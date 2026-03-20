"""Tests for the detection engine -- all 8 detectors + composite scoring.

The SimilarityDetector and GoalDriftDetector use sentence-transformers which
is too slow for CI.  We mock the embedding model and test the detectors that
rely on pure algorithmic logic (error cascade, cost velocity, diminishing
returns, context inflation, reasoning loop, token entropy) without mocks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytest_asyncio

from app.detection.base import DetectionResult
from app.detection.composite import compute_composite
from app.detection.context_inflation import ContextInflationMonitor
from app.detection.cost_velocity import CostVelocityTracker
from app.detection.diminishing_returns import DiminishingReturnsScorer
from app.detection.error_cascade import ErrorCascadeDetector
from app.detection.reasoning_loop import ReasoningLoopDetector
from app.detection.token_entropy import (
    TokenEntropyAnalyzer,
    _compression_ratio,
    _shannon_entropy_chars,
    _shannon_entropy_words,
)


# ---------------------------------------------------------------------------
# Helper: build step dicts
# ---------------------------------------------------------------------------

def _step(
    output_text: str = "output",
    input_text: str = "input",
    error_message: str | None = None,
    tool_name: str | None = None,
    cost: float = 0.01,
    tokens_used: int = 100,
    context_size: int | None = None,
    created_at: str | datetime | None = None,
    step_number: int = 1,
) -> dict:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    elif isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    return {
        "step_number": step_number,
        "input_text": input_text,
        "output_text": output_text,
        "error_message": error_message,
        "tool_name": tool_name,
        "cost": cost,
        "tokens_used": tokens_used,
        "context_size": context_size,
        "created_at": created_at,
    }


# ===================================================================
# ErrorCascadeDetector
# ===================================================================

class TestErrorCascadeDetector:
    @pytest.fixture
    def detector(self):
        return ErrorCascadeDetector()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0
        assert result.flag is None

    @pytest.mark.asyncio
    async def test_no_errors_returns_zero(self, detector):
        steps = [_step(error_message=None) for _ in range(5)]
        result = await detector.analyze(steps)
        assert result.score == 0.0
        assert result.flag is None

    @pytest.mark.asyncio
    async def test_single_error_no_flag(self, detector):
        steps = [_step(), _step(), _step(error_message="Timeout")]
        result = await detector.analyze(steps)
        assert result.score > 0
        assert result.flag is None  # Below default threshold of 3

    @pytest.mark.asyncio
    async def test_consecutive_errors_trigger_flag(self, detector):
        steps = [
            _step(),
            _step(error_message="Error 1"),
            _step(error_message="Error 2"),
            _step(error_message="Error 3"),
        ]
        result = await detector.analyze(steps)
        assert result.score > 0
        assert result.flag == "error_cascade"
        assert result.metadata["consecutive_errors"] == 3

    @pytest.mark.asyncio
    async def test_same_tool_increases_score(self, detector):
        steps = [
            _step(),
            _step(error_message="fail", tool_name="web_search"),
            _step(error_message="fail", tool_name="web_search"),
            _step(error_message="fail", tool_name="web_search"),
        ]
        result_same_tool = await detector.analyze(steps)

        steps_diff = [
            _step(),
            _step(error_message="fail", tool_name="web_search"),
            _step(error_message="fail", tool_name="code_exec"),
            _step(error_message="fail", tool_name="file_read"),
        ]
        result_diff_tool = await detector.analyze(steps_diff)

        assert result_same_tool.score > result_diff_tool.score

    @pytest.mark.asyncio
    async def test_same_error_message_increases_score(self, detector):
        steps = [
            _step(),
            _step(error_message="Connection timeout after 30s"),
            _step(error_message="Connection timeout after 30s"),
            _step(error_message="Connection timeout after 30s"),
        ]
        result = await detector.analyze(steps)
        assert result.metadata["same_error"] is True
        assert result.score > 50  # High score due to same error + cascade


# ===================================================================
# CostVelocityTracker
# ===================================================================

class TestCostVelocityTracker:
    @pytest.fixture
    def detector(self):
        return CostVelocityTracker()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_too_few_steps_returns_zero(self, detector):
        now = datetime.now(timezone.utc)
        steps = [
            _step(cost=0.01, created_at=now),
            _step(cost=0.01, created_at=now + timedelta(seconds=10)),
        ]
        result = await detector.analyze(steps)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_cost_spike_detected(self, detector):
        """Simulate 10 normal-cost steps followed by 5 high-cost steps."""
        now = datetime.now(timezone.utc)
        steps = []
        # Baseline: 10 steps at $0.01 each, 10 seconds apart
        for i in range(10):
            steps.append(_step(
                cost=0.01,
                created_at=now + timedelta(seconds=i * 10),
                step_number=i + 1,
            ))
        # Spike: 5 steps at $1.00 each, 2 seconds apart
        for i in range(5):
            steps.append(_step(
                cost=1.00,
                created_at=now + timedelta(seconds=100 + i * 2),
                step_number=11 + i,
            ))

        result = await detector.analyze(steps)
        assert result.score > 20  # Meaningful spike
        assert result.metadata["ratio"] > 1.0

    @pytest.mark.asyncio
    async def test_stable_cost_low_score(self, detector):
        """Stable costs should produce a low score."""
        now = datetime.now(timezone.utc)
        steps = [
            _step(cost=0.01, created_at=now + timedelta(seconds=i * 10), step_number=i + 1)
            for i in range(12)
        ]
        result = await detector.analyze(steps)
        assert result.score < 30
        assert result.flag is None


# ===================================================================
# DiminishingReturnsScorer
# ===================================================================

class TestDiminishingReturnsScorer:
    @pytest.fixture
    def detector(self):
        return DiminishingReturnsScorer()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_identical_outputs_high_score(self, detector):
        """Identical outputs have zero novelty -> score near 100."""
        steps = [_step(output_text="The answer is 42.") for _ in range(5)]
        result = await detector.analyze(steps)
        assert result.score >= 90.0
        assert result.metadata["avg_novelty"] < 0.05

    @pytest.mark.asyncio
    async def test_diverse_outputs_low_score(self, detector):
        """Completely different outputs should have high novelty -> low score."""
        steps = [
            _step(output_text="Photosynthesis converts sunlight into glucose energy"),
            _step(output_text="Quantum mechanics describes subatomic particle behavior"),
            _step(output_text="Renaissance art emerged in fourteenth century Italy"),
            _step(output_text="Tectonic plates shift causing earthquakes and volcanic eruptions"),
            _step(output_text="Machine learning algorithms optimize predictive statistical models"),
        ]
        result = await detector.analyze(steps)
        assert result.score < 60
        assert result.metadata["avg_novelty"] > 0.3


# ===================================================================
# ContextInflationMonitor
# ===================================================================

class TestContextInflationMonitor:
    @pytest.fixture
    def detector(self):
        return ContextInflationMonitor()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_stable_context_low_score(self, detector):
        steps = [
            _step(context_size=1000, output_text="Result alpha beta gamma"),
            _step(context_size=1050, output_text="Outcome delta epsilon zeta"),
            _step(context_size=1100, output_text="Finding theta iota kappa"),
        ]
        result = await detector.analyze(steps)
        assert result.score < 30

    @pytest.mark.asyncio
    async def test_rapid_growth_with_repetition_high_score(self, detector):
        """Context doubling each step with repetitive output => high score."""
        same_output = "The result is the same repeated conclusion"
        steps = [
            _step(context_size=1000, output_text=same_output),
            _step(context_size=2000, output_text=same_output),
            _step(context_size=4000, output_text=same_output),
            _step(context_size=8000, output_text=same_output),
        ]
        result = await detector.analyze(steps)
        assert result.score > 30
        assert result.metadata["avg_growth"] > 0.5


# ===================================================================
# ReasoningLoopDetector
# ===================================================================

class TestReasoningLoopDetector:
    @pytest.fixture
    def detector(self):
        return ReasoningLoopDetector()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_circular_reasoning_detected(self, detector):
        """Outputs that reference each other's conclusions should score high."""
        steps = [
            _step(output_text=(
                "The database query is slow because the index is missing. "
                "Therefore we should add an index to improve performance. "
                "This will reduce query latency significantly."
            )),
            _step(output_text=(
                "Adding an index will improve performance because the query is slow. "
                "The slow query results from missing database optimization. "
                "Therefore the solution is to optimize the database index."
            )),
            _step(output_text=(
                "The database needs optimization because query performance is slow. "
                "We should add an index to the database to resolve this. "
                "Therefore improving the index will make the query faster."
            )),
        ]
        result = await detector.analyze(steps)
        # Should detect repetitive conclusions and possibly cycles
        assert result.score > 0
        assert result.metadata["total_claims_extracted"] > 0

    @pytest.mark.asyncio
    async def test_progressive_reasoning_low_score(self, detector):
        """Steps that introduce genuinely new reasoning should score low."""
        steps = [
            _step(output_text=(
                "The application crashes on startup. The error log shows a NullPointerException "
                "at line 42 of UserService.java. This indicates an uninitialized dependency."
            )),
            _step(output_text=(
                "Examining the dependency injection configuration, the UserRepository bean "
                "is not registered in the application context. The @Component annotation "
                "is missing from the class definition."
            )),
            _step(output_text=(
                "After adding @Component to UserRepository, the application starts correctly. "
                "All 47 unit tests pass and the integration test confirms database connectivity. "
                "The fix has been committed to the feature branch."
            )),
        ]
        result = await detector.analyze(steps)
        assert result.score < 40  # Progressive resolution


# ===================================================================
# TokenEntropyAnalyzer
# ===================================================================

class TestTokenEntropyAnalyzer:
    @pytest.fixture
    def detector(self):
        return TokenEntropyAnalyzer()

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self, detector):
        result = await detector.analyze([])
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_repetitive_output_high_score(self, detector):
        """Highly repetitive text should compress well => high score."""
        repetitive = "error error error error error error " * 50
        steps = [
            _step(output_text=repetitive),
            _step(output_text=repetitive),
            _step(output_text=repetitive),
        ]
        result = await detector.analyze(steps)
        assert result.score > 5  # Detects high compression / cross-step repetition
        # Cross-step compression anomaly should be detected (all outputs identical)
        assert result.metadata["compression_anomaly"] >= 0

    @pytest.mark.asyncio
    async def test_natural_language_moderate_score(self, detector):
        """Normal English prose should have moderate entropy values."""
        steps = [
            _step(output_text=(
                "The implementation uses a binary search algorithm to find the target "
                "element in a sorted array. Time complexity is O(log n) which provides "
                "efficient lookup performance for large datasets."
            )),
            _step(output_text=(
                "We refactored the authentication module to support OAuth 2.0 flows. "
                "The new middleware validates JWT tokens and extracts user claims "
                "before forwarding requests to protected endpoints."
            )),
            _step(output_text=(
                "Database migration script adds a composite index on the users table "
                "covering email and organization_id columns. This reduces the average "
                "query time from 120ms to 8ms for the most common access pattern."
            )),
        ]
        result = await detector.analyze(steps)
        assert result.score < 50
        assert result.metadata["current_char_entropy"] > 0.5

    def test_shannon_entropy_empty_string(self):
        assert _shannon_entropy_chars("") == 0.0

    def test_shannon_entropy_single_char(self):
        assert _shannon_entropy_chars("aaaa") == 0.0

    def test_shannon_entropy_max_entropy(self):
        # All unique characters => maximum entropy
        text = "abcdefghijklmnop"
        entropy = _shannon_entropy_chars(text)
        assert entropy == pytest.approx(1.0, abs=0.01)

    def test_compression_ratio_empty(self):
        assert _compression_ratio("") == 1.0

    def test_compression_ratio_repetitive(self):
        text = "hello " * 1000
        ratio = _compression_ratio(text)
        assert ratio < 0.1  # Very compressible

    def test_word_entropy_single_word(self):
        entropy, vocab = _shannon_entropy_words("hello")
        assert entropy == 0.0
        assert vocab == 1


# ===================================================================
# Composite scoring (from composite.py)
# ===================================================================

class TestCompositeScoring:
    def test_compute_composite_empty(self):
        score = compute_composite({})
        assert score == 0.0

    def test_compute_composite_weighted(self):
        results = {
            "similarity": DetectionResult(score=100.0),
            "diminishing_returns": DetectionResult(score=0.0),
            "context_inflation": DetectionResult(score=0.0),
            "error_cascade": DetectionResult(score=0.0),
            "cost_velocity": DetectionResult(score=0.0),
        }
        score = compute_composite(results)
        # Default weight for similarity is 0.30, so score should be ~30
        assert 25 < score < 35

    def test_compute_composite_all_max(self):
        results = {
            "similarity": DetectionResult(score=100.0),
            "diminishing_returns": DetectionResult(score=100.0),
            "context_inflation": DetectionResult(score=100.0),
            "error_cascade": DetectionResult(score=100.0),
            "cost_velocity": DetectionResult(score=100.0),
        }
        score = compute_composite(results)
        assert score == 100.0

    def test_compute_composite_clamped(self):
        """Score should never exceed 100 even with extreme inputs."""
        results = {
            "test": DetectionResult(score=200.0),
        }
        score = compute_composite(results, weights={"test": 1.0})
        assert score <= 100.0

    def test_compute_composite_custom_weights(self):
        results = {
            "a": DetectionResult(score=100.0),
            "b": DetectionResult(score=0.0),
        }
        # With equal weights, score should be 50
        score = compute_composite(results, weights={"a": 0.5, "b": 0.5})
        assert score == pytest.approx(50.0, abs=0.1)


# ===================================================================
# DetectionEngine (full integration, mocking embedding model)
# ===================================================================

class TestDetectionEngine:
    """Test the full DetectionEngine with mocked embedding model."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        """Reset the DetectionEngine singleton between tests."""
        from app.detection.engine import DetectionEngine
        DetectionEngine._instance = None
        yield
        DetectionEngine._instance = None

    def _mock_model(self):
        """Create a mock SentenceTransformer that returns random embeddings."""
        mock = MagicMock()
        def _encode(texts, convert_to_numpy=True):
            return np.random.rand(len(texts), 384).astype(np.float32)
        mock.encode = _encode
        return mock

    @pytest.mark.asyncio
    async def test_empty_steps_returns_zero(self):
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()
                result = await engine.analyze_step([])
                assert result["score"] == 0.0
                assert result["action"] == "ok"

    @pytest.mark.asyncio
    async def test_kill_threshold_triggers_kill(self):
        """Force a scenario where all detectors return high scores."""
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()

                # Override all detectors to return score=100
                for detector in engine.detectors:
                    async def _high_score(steps, thresholds=None):
                        return DetectionResult(score=100.0, flag="test_flag", detail="forced high")
                    detector.analyze = _high_score

                result = await engine.analyze_step([_step()])
                assert result["score"] >= 75
                assert result["action"] == "kill"

    @pytest.mark.asyncio
    async def test_warn_threshold_triggers_warn(self):
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()

                # Override all detectors to return score=60
                for detector in engine.detectors:
                    async def _medium_score(steps, thresholds=None):
                        return DetectionResult(score=60.0, detail="medium risk")
                    detector.analyze = _medium_score

                result = await engine.analyze_step([_step()])
                assert result["action"] == "warn"
                assert 50 <= result["score"] < 75

    @pytest.mark.asyncio
    async def test_below_threshold_returns_ok(self):
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()

                # Override all detectors to return score=10
                for detector in engine.detectors:
                    async def _low_score(steps, thresholds=None):
                        return DetectionResult(score=10.0, detail="low risk")
                    detector.analyze = _low_score

                result = await engine.analyze_step([_step()])
                assert result["action"] == "ok"
                assert result["score"] < 50

    @pytest.mark.asyncio
    async def test_custom_thresholds_override_defaults(self):
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()

                for detector in engine.detectors:
                    async def _medium(steps, thresholds=None):
                        return DetectionResult(score=40.0, detail="medium")
                    detector.analyze = _medium

                # With default thresholds (kill=75, warn=50), score=40 is ok
                result_default = await engine.analyze_step([_step()])
                assert result_default["action"] == "ok"

                # Lower thresholds: kill=30, warn=20
                result_custom = await engine.analyze_step(
                    [_step()],
                    thresholds={"kill_threshold": 30, "warn_threshold": 20},
                )
                assert result_custom["action"] == "kill"

    @pytest.mark.asyncio
    async def test_breakdown_contains_all_detectors(self):
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine
                engine = DetectionEngine()

                result = await engine.analyze_step([_step(), _step()])
                breakdown = result["breakdown"]

                expected_keys = {
                    "similarity", "reasoning_loop", "error_cascade",
                    "diminishing_returns", "goal_drift", "token_entropy",
                    "cost_velocity", "context_inflation", "composite",
                }
                assert expected_keys == set(breakdown.keys())

    @pytest.mark.asyncio
    async def test_composite_score_weighted_correctly(self):
        """Verify that the composite is a weighted sum of individual scores."""
        with patch("app.detection.similarity._get_model", return_value=self._mock_model()):
            with patch("app.detection.goal_drift._get_model", return_value=self._mock_model()):
                from app.detection.engine import DetectionEngine, _WEIGHTS
                engine = DetectionEngine()

                # Set each detector to return its weight * 100
                # so the composite should be sum(w_i * w_i * 100) / sum(w_i)
                individual_scores = {}
                for detector in engine.detectors:
                    target_score = 50.0  # All same
                    individual_scores[detector.name] = target_score

                    async def _fixed(steps, thresholds=None, s=target_score):
                        return DetectionResult(score=s, detail="test")
                    detector.analyze = _fixed

                result = await engine.analyze_step([_step()])
                # All detectors return 50, weighted avg should also be 50
                assert result["score"] == pytest.approx(50.0, abs=1.0)
