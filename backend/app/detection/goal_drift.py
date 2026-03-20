"""Goal Drift Detector -- measures semantic distance from the original task.

This detector tracks how an agent's focus evolves over time relative to its
original objective. It operates on a fundamentally different axis than the
Similarity Detector:

- **Similarity Detector**: Measures pairwise similarity between consecutive
  outputs (detecting repetition / loops).
- **Goal Drift Detector**: Measures each output's alignment with the ORIGINAL
  TASK (detecting wandering / scope creep).

An agent can produce highly varied outputs (low similarity score) while still
drifting far from its goal (high goal drift score). Conversely, an agent can
stay on-topic (low goal drift) while repeating itself (high similarity).

Algorithm:

1. **Anchor Embedding**: Compute the embedding of the agent's first input
   (the original task prompt). This is the "north star" -- the semantic
   anchor that all subsequent outputs are measured against.

2. **Step Alignment Curve**: For each step, compute cosine similarity between
   the step's output embedding and the anchor embedding. This produces a
   time series of alignment scores in [0, 1].

3. **Drift Detection**: Analyze the alignment curve for:
   - **Sustained decline**: A monotonically decreasing trend indicates the
     agent is gradually losing focus. Measured via linear regression slope.
   - **Sudden drop**: A single-step drop > 0.3 in alignment indicates an
     abrupt topic change (the agent "jumped" to something unrelated).
   - **Low terminal alignment**: The most recent alignment score being < 0.3
     means the agent is currently far from its goal.

4. **Purposeful Pivot Detection**: Not all drift is bad. If the agent's
   output explicitly references the original task while exploring a subtopic,
   that's a purposeful pivot. We detect this by checking if the original
   task's key terms appear in outputs with low alignment -- if they do, the
   penalty is reduced.

Scoring:
- alignment_decline_rate: up to 40 points (scaled by slope magnitude)
- current_alignment_penalty: up to 30 points (inverse of current alignment)
- sudden_drop_penalty: up to 20 points (number and severity of drops)
- purposeful_pivot_discount: reduces score by up to 15 points

Flag: "goal_drift" when composite score exceeds threshold.
"""

from __future__ import annotations

import asyncio
import functools
import re
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from .base import BaseDetector, DetectionResult


def _get_model():
    """Reuse the singleton embedding model from similarity detector."""
    from .similarity import _get_model as _sim_get_model
    return _sim_get_model()


def _compute_goal_drift(
    anchor_text: str,
    outputs: list[str],
    original_task_tokens: set[str],
) -> dict:
    """Compute goal drift metrics synchronously (CPU-bound).

    Returns a dict with all computed metrics for scoring.
    """
    model = _get_model()

    # Encode anchor and all outputs in a single batch for efficiency
    all_texts = [anchor_text] + outputs
    embeddings = model.encode(all_texts, convert_to_numpy=True)

    anchor_emb = embeddings[0:1]  # shape (1, dim)
    output_embs = embeddings[1:]  # shape (N, dim)

    # Compute alignment: cosine similarity of each output with the anchor
    alignment_scores: list[float] = []
    for i in range(len(outputs)):
        sim = float(sklearn_cosine(anchor_emb, output_embs[i:i+1])[0][0])
        alignment_scores.append(max(0.0, min(1.0, sim)))

    # --- Alignment decline via linear regression ---
    n = len(alignment_scores)
    decline_slope = 0.0
    if n >= 2:
        x = np.arange(n, dtype=float)
        y = np.array(alignment_scores, dtype=float)
        x_mean = x.mean()
        y_mean = y.mean()
        numerator = float(np.sum((x - x_mean) * (y - y_mean)))
        denominator = float(np.sum((x - x_mean) ** 2))
        if denominator > 0:
            decline_slope = numerator / denominator
        # Negative slope = declining alignment = drift

    # --- Sudden drops ---
    sudden_drops: list[dict] = []
    for i in range(1, n):
        drop = alignment_scores[i - 1] - alignment_scores[i]
        if drop > 0.25:
            sudden_drops.append({
                "step": i,
                "from": round(alignment_scores[i - 1], 4),
                "to": round(alignment_scores[i], 4),
                "magnitude": round(drop, 4),
            })

    # --- Current (terminal) alignment ---
    current_alignment = alignment_scores[-1] if alignment_scores else 1.0

    # --- Purposeful pivot detection ---
    # Check if low-alignment outputs still reference original task terms
    pivot_discount = 0.0
    low_alignment_outputs = [
        (i, outputs[i]) for i in range(n) if alignment_scores[i] < 0.4
    ]
    if low_alignment_outputs and original_task_tokens:
        references_found = 0
        for _, text in low_alignment_outputs:
            text_tokens = set(re.findall(r"\w+", text.lower()))
            overlap = text_tokens & original_task_tokens
            # If at least 30% of original task tokens appear, it's a pivot
            if len(overlap) / max(len(original_task_tokens), 1) >= 0.3:
                references_found += 1
        pivot_ratio = references_found / len(low_alignment_outputs)
        pivot_discount = pivot_ratio * 15.0  # Up to 15 points discount

    return {
        "alignment_scores": alignment_scores,
        "decline_slope": decline_slope,
        "sudden_drops": sudden_drops,
        "current_alignment": current_alignment,
        "pivot_discount": pivot_discount,
        "embeddings": embeddings.tolist(),
    }


class GoalDriftDetector(BaseDetector):
    """Detects when an agent's outputs drift away from its original task.

    Uses embedding-based semantic distance tracking with trend analysis
    to distinguish productive exploration from aimless wandering.
    """

    name = "goal_drift"
    default_weight = 0.10

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        window = thresholds.get("goal_drift_window", 8)

        if len(steps) < 2:
            return DetectionResult(
                score=0.0, detail="Not enough steps to measure goal drift"
            )

        # The anchor is the FIRST step's input -- the original task
        anchor_text = ""
        for step in steps:
            text = (step.get("input_text") or step.get("output_text") or "").strip()
            if text:
                anchor_text = text
                break

        if not anchor_text:
            return DetectionResult(
                score=0.0, detail="No anchor text found for goal drift analysis"
            )

        # Collect recent outputs
        recent_steps = steps[-window:]
        outputs: list[str] = []
        for step in recent_steps:
            text = (step.get("output_text") or "").strip()
            if text:
                outputs.append(text)

        if len(outputs) < 2:
            return DetectionResult(
                score=0.0, detail="Not enough outputs to measure goal drift"
            )

        # Extract key tokens from original task for pivot detection
        _STOP_WORDS = frozenset({
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
            "has", "had", "do", "does", "did", "will", "would", "could", "should",
            "may", "might", "can", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "as", "and", "but", "or", "not", "no", "so", "if",
            "then", "that", "this", "it", "i", "me", "my", "we", "you", "your",
            "please", "help", "want", "need",
        })
        original_task_tokens = (
            set(re.findall(r"\w+", anchor_text.lower())) - _STOP_WORDS
        )

        # Run CPU-bound computation in thread pool
        loop = asyncio.get_event_loop()
        metrics = await loop.run_in_executor(
            None,
            functools.partial(
                _compute_goal_drift, anchor_text, outputs, original_task_tokens
            ),
        )

        # ----- Score computation -----
        decline_slope = metrics["decline_slope"]
        current_alignment = metrics["current_alignment"]
        sudden_drops = metrics["sudden_drops"]
        pivot_discount = metrics["pivot_discount"]

        # Alignment decline: negative slope penalized
        decline_penalty = 0.0
        if decline_slope < -0.02:  # Meaningful decline
            decline_penalty = min(abs(decline_slope) * 400, 40.0)

        # Current alignment penalty: lower alignment = higher penalty
        alignment_penalty = 0.0
        if current_alignment < 0.5:
            alignment_penalty = (1.0 - current_alignment) * 30.0

        # Sudden drop penalty
        drop_penalty = 0.0
        for drop in sudden_drops:
            drop_penalty += drop["magnitude"] * 20.0
        drop_penalty = min(drop_penalty, 20.0)

        raw_score = decline_penalty + alignment_penalty + drop_penalty
        score = max(0.0, raw_score - pivot_discount)
        score = round(min(score, 100.0), 2)

        flag_threshold = thresholds.get("goal_drift", 30)
        flag = "goal_drift" if score >= flag_threshold else None

        detail_parts = []
        if decline_penalty > 5:
            detail_parts.append(
                f"alignment declining (slope: {decline_slope:.4f})"
            )
        if alignment_penalty > 5:
            detail_parts.append(
                f"current alignment low ({current_alignment:.3f})"
            )
        if sudden_drops:
            detail_parts.append(f"{len(sudden_drops)} sudden topic change(s)")
        if pivot_discount > 0:
            detail_parts.append(f"purposeful pivot detected (-{pivot_discount:.1f})")

        detail = "; ".join(detail_parts) if detail_parts else "Goal alignment stable"

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "alignment_scores": metrics["alignment_scores"],
                "decline_slope": decline_slope,
                "current_alignment": current_alignment,
                "sudden_drops": sudden_drops,
                "pivot_discount": pivot_discount,
                "decline_penalty": decline_penalty,
                "alignment_penalty": alignment_penalty,
                "drop_penalty": drop_penalty,
                "anchor_text_length": len(anchor_text),
            },
        )
