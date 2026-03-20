from __future__ import annotations

import re
from typing import Any

from .base import BaseDetector, DetectionResult


class ContextInflationMonitor(BaseDetector):
    name = "context_inflation"
    default_weight = 0.08

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        growth_threshold = thresholds.get("context_inflation_growth", 0.20)
        novelty_threshold = thresholds.get("context_inflation_novelty", 0.15)

        # Filter steps that have a non-null context_size
        sized_steps: list[dict[str, Any]] = [
            s for s in steps if s.get("context_size") is not None
        ]

        if len(sized_steps) < 2:
            return DetectionResult(
                score=0.0, detail="Not enough steps with context_size"
            )

        # Calculate growth rates between consecutive steps
        growth_rates: list[float] = []
        for i in range(1, len(sized_steps)):
            prev_size = sized_steps[i - 1]["context_size"]
            curr_size = sized_steps[i]["context_size"]
            if prev_size > 0:
                rate = (curr_size - prev_size) / prev_size
            else:
                rate = 0.0
            growth_rates.append(rate)

        avg_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0.0

        # Estimate output novelty via simple token overlap between consecutive outputs
        overlap_ratios: list[float] = []
        for i in range(1, len(sized_steps)):
            prev_text = (sized_steps[i - 1].get("output_text") or "").strip()
            curr_text = (sized_steps[i].get("output_text") or "").strip()

            prev_tokens = set(re.findall(r"\w+", prev_text.lower()))
            curr_tokens = set(re.findall(r"\w+", curr_text.lower()))

            if curr_tokens:
                new_tokens = curr_tokens - prev_tokens
                novelty = len(new_tokens) / len(curr_tokens)
            else:
                novelty = 0.0
            overlap_ratios.append(novelty)

        output_novelty = (
            sum(overlap_ratios) / len(overlap_ratios) if overlap_ratios else 0.0
        )

        # Score: growth-driven, damped by novelty
        raw_score = max(0.0, avg_growth * 100) * (1 - output_novelty)
        score = round(min(raw_score, 100.0), 2)

        flag = None
        if avg_growth > growth_threshold and output_novelty < novelty_threshold:
            flag = "context_bloat"

        detail = (
            f"Avg context growth {avg_growth:.3f}, "
            f"output novelty {output_novelty:.3f}"
        )

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "growth_rates": growth_rates,
                "avg_growth": avg_growth,
                "output_novelty": output_novelty,
                "overlap_ratios": overlap_ratios,
            },
        )
