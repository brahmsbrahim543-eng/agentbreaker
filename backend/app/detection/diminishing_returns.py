from __future__ import annotations

import re
from typing import Any

from .base import BaseDetector, DetectionResult


class DiminishingReturnsScorer(BaseDetector):
    name = "diminishing_returns"
    default_weight = 0.12

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        novelty_threshold = thresholds.get("diminishing_returns", 0.10)
        window = 5

        # Collect up to the last `window` steps that have output text
        recent: list[str] = []
        for step in steps[-window:]:
            text = (step.get("output_text") or "").strip()
            recent.append(text)

        if len(recent) < 2:
            return DetectionResult(
                score=0.0, detail="Not enough steps to measure novelty"
            )

        # Tokenize each output
        tokenized: list[set[str]] = []
        for text in recent:
            tokens = set(re.findall(r"\w+", text.lower()))
            tokenized.append(tokens)

        # Track cumulative seen tokens and compute novelty ratios
        seen_tokens: set[str] = set(tokenized[0])
        novelty_ratios: list[float] = []

        for step_tokens in tokenized[1:]:
            new_tokens = step_tokens - seen_tokens
            novelty_ratio = len(new_tokens) / max(len(step_tokens), 1)
            novelty_ratios.append(novelty_ratio)
            seen_tokens |= step_tokens

        avg_novelty = sum(novelty_ratios) / len(novelty_ratios) if novelty_ratios else 1.0
        score = round((1 - avg_novelty) * 100, 2)

        flag = "diminishing_returns" if avg_novelty < novelty_threshold else None
        detail = (
            f"Avg novelty ratio {avg_novelty:.3f} over {len(novelty_ratios)} transitions"
        )

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "novelty_ratios": novelty_ratios,
                "avg_novelty": avg_novelty,
                "total_unique_tokens": len(seen_tokens),
            },
        )
