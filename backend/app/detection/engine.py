"""Detection Engine -- orchestrates all detectors and produces a composite risk score."""

from __future__ import annotations

import asyncio

from app.detection.similarity import SimilarityDetector
from app.detection.diminishing_returns import DiminishingReturnsScorer
from app.detection.context_inflation import ContextInflationMonitor
from app.detection.error_cascade import ErrorCascadeDetector
from app.detection.cost_velocity import CostVelocityTracker
from app.detection.reasoning_loop import ReasoningLoopDetector
from app.detection.goal_drift import GoalDriftDetector
from app.detection.token_entropy import TokenEntropyAnalyzer
from app.detection.base import DetectionResult


# Explicit weight table -- must sum to 1.00
_WEIGHTS: dict[str, float] = {
    "similarity": 0.20,
    "reasoning_loop": 0.15,
    "error_cascade": 0.15,
    "diminishing_returns": 0.12,
    "goal_drift": 0.10,
    "token_entropy": 0.10,
    "cost_velocity": 0.10,
    "context_inflation": 0.08,
}


class DetectionEngine:
    """Singleton detection engine that runs all registered detectors."""

    _instance: DetectionEngine | None = None

    def __new__(cls) -> DetectionEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self.detectors = [
            SimilarityDetector(),
            DiminishingReturnsScorer(),
            ContextInflationMonitor(),
            ErrorCascadeDetector(),
            CostVelocityTracker(),
            ReasoningLoopDetector(),
            GoalDriftDetector(),
            TokenEntropyAnalyzer(),
        ]
        # Apply explicit weights, overriding detector defaults
        self.weights = {
            d.name: _WEIGHTS.get(d.name, d.default_weight)
            for d in self.detectors
        }

    async def analyze_step(
        self,
        steps: list[dict],
        thresholds: dict | None = None,
    ) -> dict:
        """Run all detectors in parallel and compute a composite risk score.

        Returns dict with keys: score, action, breakdown, warnings, flags.
        """
        thresholds = thresholds or {}
        kill_threshold = thresholds.get("kill_threshold", 75)
        warn_threshold = thresholds.get("warn_threshold", 50)

        # Run all detectors in parallel
        tasks = [detector.analyze(steps, thresholds) for detector in self.detectors]
        detector_results = await asyncio.gather(*tasks)

        results: dict[str, DetectionResult] = {}
        for detector, result in zip(self.detectors, detector_results):
            results[detector.name] = result

        total_weight = sum(self.weights.values())
        composite = 0.0
        for name, result in results.items():
            weight = self.weights.get(name, 0.0)
            composite += result.score * (weight / total_weight)

        composite = round(min(composite, 100.0), 2)

        flags = [r.flag for r in results.values() if r.flag]
        warnings = [r.detail for r in results.values() if r.score > 30]

        if composite >= kill_threshold:
            action = "kill"
        elif composite >= warn_threshold:
            action = "warn"
        else:
            action = "ok"

        breakdown = {
            d.name: results.get(d.name, DetectionResult(score=0.0, detail="")).score
            for d in self.detectors
        }
        breakdown["composite"] = composite

        return {
            "score": composite,
            "action": action,
            "breakdown": breakdown,
            "warnings": warnings,
            "flags": flags,
        }
