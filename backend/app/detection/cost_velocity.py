from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import BaseDetector, DetectionResult


class CostVelocityTracker(BaseDetector):
    name = "cost_velocity"
    default_weight = 0.10

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        ratio_threshold = thresholds.get("cost_velocity", 3.0)
        window = 5

        # Filter steps that have both cost and created_at
        valid_steps: list[dict[str, Any]] = []
        for s in steps:
            cost = s.get("cost")
            created_at = s.get("created_at")
            if cost is not None and created_at is not None:
                valid_steps.append(s)

        if len(valid_steps) < 3:
            return DetectionResult(
                score=0.0, detail="Not enough steps with cost data"
            )

        def _parse_dt(val: Any) -> datetime:
            if isinstance(val, datetime):
                # Strip timezone info to avoid naive/aware comparison issues
                return val.replace(tzinfo=None)
            dt = datetime.fromisoformat(str(val))
            return dt.replace(tzinfo=None)

        def _velocity(segment: list[dict[str, Any]]) -> float:
            """Cost per second for a segment of steps."""
            if len(segment) < 2:
                return 0.0
            total_cost = sum(float(s["cost"]) for s in segment)
            t_start = _parse_dt(segment[0]["created_at"])
            t_end = _parse_dt(segment[-1]["created_at"])
            duration = (t_end - t_start).total_seconds()
            if duration <= 0:
                return 0.0
            return total_cost / duration

        # Current window = last `window` steps
        current_segment = valid_steps[-window:]
        current_velocity = _velocity(current_segment)

        # Baseline = everything before the current window
        baseline_segment = valid_steps[:-window] if len(valid_steps) > window else []
        baseline_velocity = _velocity(baseline_segment)

        ratio = current_velocity / max(baseline_velocity, 0.0001)
        score = round(min(ratio * 20, 100.0), 2)

        flag = "cost_spike" if ratio > ratio_threshold else None
        detail = (
            f"Current velocity {current_velocity:.6f}/s, "
            f"baseline {baseline_velocity:.6f}/s, ratio {ratio:.2f}"
        )

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "current_velocity": current_velocity,
                "baseline_velocity": baseline_velocity,
                "ratio": ratio,
            },
        )
