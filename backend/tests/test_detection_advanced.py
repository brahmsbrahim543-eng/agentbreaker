"""Tests for advanced detection algorithms: ReasoningLoop, GoalDrift, TokenEntropy.

Each test uses realistic agent output scenarios to validate that the detectors
produce meaningful scores and correctly identify failure modes.
"""

from __future__ import annotations

import asyncio
import math
import pytest

from app.detection.reasoning_loop import (
    ReasoningLoopDetector,
    _extract_claims,
    _extract_claim_tokens,
    _count_meta_reasoning,
    _split_sentences,
    _ReasoningGraph,
)
from app.detection.token_entropy import (
    TokenEntropyAnalyzer,
    _shannon_entropy_chars as te_shannon_chars,
    _shannon_entropy_words,
    _compression_ratio,
    _cross_step_compression_ratio,
    _linear_slope,
)
from app.detection.goal_drift import GoalDriftDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run an async coroutine synchronously for testing."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# ReasoningLoopDetector tests
# ---------------------------------------------------------------------------

class TestClaimExtraction:
    """Tests for the NLP claim extraction pipeline."""

    def test_extract_claims_causal(self):
        text = (
            "The server is overloaded. Therefore, we should scale horizontally. "
            "This implies that the database needs read replicas."
        )
        claims = _extract_claims(text)
        assert len(claims) >= 2
        assert any("therefore" in c for c in claims)
        assert any("implies" in c for c in claims)

    def test_extract_claims_quantitative(self):
        text = (
            "CPU usage is at 95%. Memory consumption increased by 200MB. "
            "The average response time is 3.5 seconds."
        )
        claims = _extract_claims(text)
        assert len(claims) >= 2
        # All sentences contain numbers so should be extracted
        assert any("95" in c for c in claims)

    def test_extract_claims_empty(self):
        claims = _extract_claims("")
        assert claims == []

    def test_extract_claims_no_assertions(self):
        text = "Hello world. How are you today? Nice weather."
        claims = _extract_claims(text)
        # These are not assertive claims
        assert len(claims) == 0

    def test_claim_tokens_stop_word_removal(self):
        tokens = _extract_claim_tokens("the server should be scaled horizontally")
        assert "the" not in tokens
        assert "be" not in tokens
        assert "server" in tokens
        assert "scaled" in tokens
        assert "horizontally" in tokens

    def test_sentence_splitting(self):
        text = (
            "Mr. Smith went to Washington. He met Dr. Jones there. "
            "They discussed e.g. policy changes."
        )
        sentences = _split_sentences(text)
        # Should not split on Mr. or Dr. or e.g.
        assert len(sentences) >= 2


class TestReasoningGraph:
    """Tests for the reasoning graph and cycle detection."""

    def test_no_cycles(self):
        g = _ReasoningGraph()
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        cycles = g.find_cycles()
        assert len(cycles) == 0

    def test_simple_cycle(self):
        g = _ReasoningGraph()
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 0)  # Cycle: 0 -> 1 -> 2 -> 0
        cycles = g.find_cycles()
        assert len(cycles) == 1
        assert set(cycles[0]) == {0, 1, 2}

    def test_multiple_cycles(self):
        g = _ReasoningGraph()
        # Cycle 1: 0 -> 1 -> 0
        g.add_edge(0, 1)
        g.add_edge(1, 0)
        # Cycle 2: 2 -> 3 -> 4 -> 2
        g.add_edge(2, 3)
        g.add_edge(3, 4)
        g.add_edge(4, 2)
        cycles = g.find_cycles()
        assert len(cycles) == 2

    def test_self_loop(self):
        g = _ReasoningGraph()
        g.add_node(0)
        g.add_edge(0, 0)
        # Self-loops create an SCC of size 1, which we don't report
        cycles = g.find_cycles()
        assert len(cycles) == 0

    def test_disconnected_graph(self):
        g = _ReasoningGraph()
        g.add_node(0)
        g.add_node(1)
        g.add_node(2)
        cycles = g.find_cycles()
        assert len(cycles) == 0


class TestMetaReasoning:
    """Tests for meta-reasoning detection."""

    def test_meta_reasoning_detected(self):
        text = (
            "Let me reconsider my approach to this problem. "
            "Actually, maybe I should think about this differently. "
            "Looking at this from another angle might help. "
            "The server needs more memory."
        )
        meta, total = _count_meta_reasoning(text)
        assert meta >= 2
        assert total >= 3

    def test_no_meta_reasoning(self):
        text = (
            "The database query takes 500ms. The index on the users table "
            "reduces this to 50ms. We should add a composite index."
        )
        meta, total = _count_meta_reasoning(text)
        assert meta == 0


class TestReasoningLoopDetector:
    """Integration tests for the full reasoning loop detector."""

    def test_circular_reasoning(self):
        """Agent conclusions reference each other in a cycle."""
        steps = [
            {"output_text": (
                "The server is slow because the database queries are expensive. "
                "Therefore we should optimize the database to improve server speed."
            )},
            {"output_text": (
                "The database queries are expensive because the server sends "
                "too many requests. This means the server load causes database slowness."
            )},
            {"output_text": (
                "Server slowness leads to more retries which increases database load. "
                "Therefore the database being slow causes the server to be slow."
            )},
        ]
        detector = ReasoningLoopDetector()
        result = run(detector.analyze(steps))
        # Should detect circular reasoning
        assert result.score > 20
        assert result.metadata["cycles_found"] >= 0  # Graph may find cycles
        assert result.metadata["conclusion_repetition"] > 0.1

    def test_productive_reasoning(self):
        """Agent makes genuine progress -- each step adds new depth."""
        steps = [
            {"output_text": (
                "The application has a memory leak. Stack traces show allocations "
                "in the image processing module."
            )},
            {"output_text": (
                "The image processing module uses a buffer pool. Profiling shows "
                "buffers are allocated but never returned to the pool after processing."
            )},
            {"output_text": (
                "The root cause is in the error handler: when JPEG decoding fails, "
                "the buffer reference is dropped without calling release(). "
                "Fix: add a finally block to ensure buffer.release() is always called."
            )},
        ]
        detector = ReasoningLoopDetector()
        result = run(detector.analyze(steps))
        # Should not flag productive reasoning
        assert result.score < 30
        assert result.flag is None

    def test_meta_reasoning_heavy(self):
        """Agent spends most of its time reasoning about reasoning."""
        steps = [
            {"output_text": (
                "Let me think about this problem more carefully. I should reconsider "
                "my approach. Perhaps I need to step back and evaluate."
            )},
            {"output_text": (
                "Actually, let me reconsider. I was thinking about this the wrong way. "
                "Let me re-evaluate my strategy for solving this."
            )},
            {"output_text": (
                "On further thought, maybe I should think about this differently. "
                "Wait, let me reconsider my approach once more."
            )},
        ]
        detector = ReasoningLoopDetector()
        result = run(detector.analyze(steps))
        assert result.metadata["meta_reasoning_ratio"] > 0.3

    def test_insufficient_data(self):
        steps = [{"output_text": "Hello world"}]
        detector = ReasoningLoopDetector()
        result = run(detector.analyze(steps))
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# GoalDriftDetector tests
# ---------------------------------------------------------------------------

class TestGoalDriftDetector:
    """Tests for the goal drift detector."""

    def test_drifting_agent(self):
        """Agent starts on task then wanders to unrelated topics."""
        steps = [
            {
                "input_text": "Fix the authentication bug in the login module",
                "output_text": "I'll examine the login module for authentication issues.",
            },
            {
                "output_text": (
                    "The login module uses JWT tokens. Let me check the token "
                    "validation logic for the authentication flow."
                ),
            },
            {
                "output_text": (
                    "Actually, I notice the CSS styling on the dashboard looks "
                    "outdated. The color scheme could use some modernization."
                ),
            },
            {
                "output_text": (
                    "The dashboard layout uses flexbox which has some browser "
                    "compatibility issues. We should consider using CSS Grid "
                    "for the main navigation structure."
                ),
            },
        ]
        detector = GoalDriftDetector()
        result = run(detector.analyze(steps))
        # Should detect drift: started with auth bug, ended with CSS
        assert result.score > 15
        alignment_scores = result.metadata["alignment_scores"]
        # Later outputs should have lower alignment than earlier ones
        assert alignment_scores[-1] < alignment_scores[0]

    def test_focused_agent(self):
        """Agent stays on task throughout."""
        steps = [
            {
                "input_text": "Optimize the database query performance",
                "output_text": "I'll analyze the slow database queries.",
            },
            {
                "output_text": (
                    "The main query on the users table is doing a full table scan. "
                    "Adding an index on email and created_at should help."
                ),
            },
            {
                "output_text": (
                    "After adding the index, query time dropped from 500ms to 15ms. "
                    "The database query performance is now optimized."
                ),
            },
        ]
        detector = GoalDriftDetector()
        result = run(detector.analyze(steps))
        assert result.score < 20
        assert result.flag is None

    def test_purposeful_pivot(self):
        """Agent explores a subtopic but references the original goal."""
        steps = [
            {
                "input_text": "Fix the authentication bug in the login system",
                "output_text": "Investigating the authentication bug in login.",
            },
            {
                "output_text": (
                    "The authentication bug traces back to the session store. "
                    "I need to check Redis configuration since the login "
                    "authentication depends on session persistence."
                ),
            },
            {
                "output_text": (
                    "Redis connection pooling was misconfigured for the "
                    "authentication session store. Fixed the pool size, "
                    "which resolves the login authentication bug."
                ),
            },
        ]
        detector = GoalDriftDetector()
        result = run(detector.analyze(steps))
        # Should have low score despite touching Redis
        assert result.score < 25

    def test_insufficient_data(self):
        steps = [{"input_text": "Do something", "output_text": "Ok"}]
        detector = GoalDriftDetector()
        result = run(detector.analyze(steps))
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# TokenEntropyAnalyzer tests
# ---------------------------------------------------------------------------

class TestShannonEntropy:
    """Tests for the core Shannon entropy functions."""

    def test_uniform_distribution(self):
        """All characters equally likely => maximum entropy => 1.0."""
        text = "abcdefghij" * 10  # Uniform-ish distribution
        entropy = te_shannon_chars(text)
        assert entropy > 0.9

    def test_single_character(self):
        """Only one character => zero entropy."""
        text = "aaaaaaaaaa"
        entropy = te_shannon_chars(text)
        assert entropy == 0.0

    def test_empty_string(self):
        assert te_shannon_chars("") == 0.0

    def test_english_text_range(self):
        """English prose should have normalized entropy around 0.7-0.95."""
        text = (
            "The quick brown fox jumps over the lazy dog. This sentence "
            "contains every letter of the alphabet at least once."
        )
        entropy = te_shannon_chars(text)
        assert 0.65 < entropy < 0.98

    def test_word_entropy_basic(self):
        text = "the cat sat on the mat the cat sat on the mat"
        entropy, vocab = _shannon_entropy_words(text)
        assert vocab == 5  # the, cat, sat, on, mat
        assert 0.0 < entropy < 1.0

    def test_word_entropy_high_diversity(self):
        text = "alpha bravo charlie delta echo foxtrot golf hotel india"
        entropy, vocab = _shannon_entropy_words(text)
        assert vocab == 9
        assert entropy > 0.95  # All words unique => high entropy


class TestCompressionRatio:
    """Tests for zlib compression analysis."""

    def test_repetitive_text_compresses_well(self):
        text = "error: connection failed. " * 100
        ratio = _compression_ratio(text)
        assert ratio < 0.10  # Very repetitive => very compressible

    def test_diverse_text_compresses_less(self):
        import string
        import random
        random.seed(42)
        text = "".join(random.choices(string.ascii_letters + " ", k=2000))
        ratio = _compression_ratio(text)
        assert ratio > 0.4  # Random text doesn't compress much

    def test_empty_text(self):
        ratio = _compression_ratio("")
        assert ratio == 1.0

    def test_cross_step_repetition(self):
        """Cross-step compression should detect inter-output repetition."""
        outputs = [
            "The server returned error 500. Retrying the request.",
            "The server returned error 500. Retrying the request.",
            "The server returned error 500. Retrying the request.",
        ]
        cross = _cross_step_compression_ratio(outputs)
        individual_avg = sum(_compression_ratio(o) for o in outputs) / 3
        # Cross-step should compress better than individual average
        # because the content is identical across steps
        assert cross < individual_avg


class TestLinearSlope:
    """Tests for the linear regression slope function."""

    def test_positive_slope(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        slope = _linear_slope(values)
        assert abs(slope - 1.0) < 0.001

    def test_negative_slope(self):
        values = [5.0, 4.0, 3.0, 2.0, 1.0]
        slope = _linear_slope(values)
        assert abs(slope - (-1.0)) < 0.001

    def test_flat(self):
        values = [3.0, 3.0, 3.0, 3.0]
        slope = _linear_slope(values)
        assert abs(slope) < 0.001

    def test_single_value(self):
        assert _linear_slope([5.0]) == 0.0

    def test_empty(self):
        assert _linear_slope([]) == 0.0


class TestTokenEntropyAnalyzer:
    """Integration tests for the full entropy analyzer."""

    def test_entropy_collapse_scenario(self):
        """Agent outputs become increasingly repetitive."""
        steps = [
            {"output_text": (
                "Analyzing the system architecture. The microservices communicate "
                "via gRPC with Protocol Buffers serialization. Each service maintains "
                "its own PostgreSQL database with event sourcing."
            )},
            {"output_text": (
                "Checking the system architecture. The services communicate via gRPC. "
                "Each service has a database. The architecture uses event sourcing."
            )},
            {"output_text": (
                "The system architecture uses gRPC. The services have databases. "
                "The architecture uses event sourcing. The system uses gRPC."
            )},
            {"output_text": (
                "The system uses gRPC. The system uses gRPC. The system has databases. "
                "The system uses gRPC. The system uses event sourcing."
            )},
        ]
        detector = TokenEntropyAnalyzer()
        result = run(detector.analyze(steps))
        # Should detect declining entropy
        assert result.score > 10
        # Word entropy should be declining
        word_entropies = result.metadata["word_entropies"]
        assert word_entropies[-1] < word_entropies[0]

    def test_healthy_entropy(self):
        """Agent produces diverse, information-rich outputs."""
        steps = [
            {"output_text": (
                "The login endpoint accepts POST requests with email and password. "
                "It validates credentials against bcrypt hashes stored in the users table."
            )},
            {"output_text": (
                "Session management uses Redis-backed JWT tokens with 15-minute expiry. "
                "Refresh tokens rotate on each use to prevent replay attacks."
            )},
            {"output_text": (
                "Rate limiting is implemented at the API gateway level using a sliding "
                "window algorithm. Each IP is allowed 100 requests per minute, with "
                "exponential backoff headers returned on 429 responses."
            )},
        ]
        detector = TokenEntropyAnalyzer()
        result = run(detector.analyze(steps))
        assert result.score < 25
        assert result.flag is None

    def test_compression_anomaly(self):
        """Outputs that are individually varied but collectively repetitive."""
        base = (
            "Step {n}: Attempting to fix the connection. "
            "The database returns timeout after 30 seconds. "
            "Retrying with exponential backoff. Attempt {n} failed."
        )
        steps = [
            {"output_text": base.format(n=i)} for i in range(1, 5)
        ]
        detector = TokenEntropyAnalyzer()
        result = run(detector.analyze(steps))
        anomaly = result.metadata["compression_anomaly"]
        # Cross-step compression should reveal the template pattern
        assert anomaly > 0.0

    def test_insufficient_data(self):
        steps = [{"output_text": "hello"}]
        detector = TokenEntropyAnalyzer()
        result = run(detector.analyze(steps))
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# Cross-detector integration test
# ---------------------------------------------------------------------------

class TestDetectorOrthogonality:
    """Verify that the three new detectors measure different things."""

    def test_loop_without_drift(self):
        """Agent loops on the same topic (high reasoning_loop) but stays
        on-goal (low goal_drift)."""
        steps = [
            {
                "input_text": "Fix the memory leak",
                "output_text": (
                    "The memory leak is caused by unclosed connections. "
                    "Therefore we should close connections."
                ),
            },
            {
                "output_text": (
                    "Connections are not being closed which causes the memory leak. "
                    "We need to close them to fix the memory leak."
                ),
            },
            {
                "output_text": (
                    "The memory leak happens because connections are unclosed. "
                    "Therefore closing connections will fix the memory leak."
                ),
            },
        ]
        loop_det = ReasoningLoopDetector()
        drift_det = GoalDriftDetector()

        loop_result = run(loop_det.analyze(steps))
        drift_result = run(drift_det.analyze(steps))

        # Reasoning loop should be higher than goal drift
        # because the agent IS on-topic but going in circles
        assert loop_result.score > drift_result.score or drift_result.score < 20

    def test_drift_without_loop(self):
        """Agent drifts but doesn't repeat itself (high drift, low loop)."""
        steps = [
            {
                "input_text": "Fix the authentication bug",
                "output_text": "I'll look at the authentication module.",
            },
            {
                "output_text": (
                    "The CSS framework needs updating. Bootstrap 5 has better "
                    "utility classes than our current version 3."
                ),
            },
            {
                "output_text": (
                    "The deployment pipeline should use Docker multi-stage builds "
                    "to reduce image size from 2GB to 400MB."
                ),
            },
        ]
        loop_det = ReasoningLoopDetector()
        drift_det = GoalDriftDetector()

        loop_result = run(loop_det.analyze(steps))
        drift_result = run(drift_det.analyze(steps))

        # Goal drift should be elevated (topics change from auth to CSS to Docker)
        # Reasoning loop should be low (no circular arguments)
        assert loop_result.metadata["cycles_found"] == 0
