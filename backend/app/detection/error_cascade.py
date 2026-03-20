from __future__ import annotations

from typing import Any

from .base import BaseDetector, DetectionResult


class ErrorCascadeDetector(BaseDetector):
    name = "error_cascade"
    default_weight = 0.15

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        error_threshold = thresholds.get("error_cascade", 3)
        window_size = max(len(steps), 1)

        if not steps:
            return DetectionResult(score=0.0, detail="No steps to analyze")

        # Count consecutive errors from the end (most recent)
        consecutive_errors = 0
        error_steps: list[dict[str, Any]] = []

        for step in reversed(steps):
            error_msg = step.get("error_message")
            if error_msg is not None and str(error_msg).strip():
                consecutive_errors += 1
                error_steps.append(step)
            else:
                break

        if consecutive_errors == 0:
            return DetectionResult(
                score=0.0,
                detail="No consecutive errors at tail",
                metadata={"consecutive_errors": 0},
            )

        # Check if same tool_name repeats across the error run
        tool_names = [
            s.get("tool_name") for s in error_steps if s.get("tool_name")
        ]
        same_tool = (
            len(set(tool_names)) == 1 and len(tool_names) == consecutive_errors
            if tool_names
            else False
        )

        # Check if same error_message repeats (compare first 50 chars)
        error_prefixes = [
            str(s.get("error_message", ""))[:50] for s in error_steps
        ]
        same_error = (
            len(set(error_prefixes)) == 1 and len(error_prefixes) == consecutive_errors
        )

        # Scoring
        base_score = (consecutive_errors / window_size) * 100
        if same_tool:
            base_score += 15
        if same_error:
            base_score += 15

        score = round(min(base_score, 100.0), 2)

        flag = "error_cascade" if consecutive_errors >= error_threshold else None
        detail = (
            f"{consecutive_errors} consecutive errors"
            f"{', same tool' if same_tool else ''}"
            f"{', same message' if same_error else ''}"
        )

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "consecutive_errors": consecutive_errors,
                "same_tool": same_tool,
                "same_error": same_error,
                "tool_names": tool_names,
                "error_prefixes": error_prefixes,
            },
        )
