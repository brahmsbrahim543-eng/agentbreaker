from __future__ import annotations

from .base import DetectionResult

DEFAULT_WEIGHTS: dict[str, float] = {
    "similarity": 0.30,
    "diminishing_returns": 0.20,
    "context_inflation": 0.15,
    "error_cascade": 0.20,
    "cost_velocity": 0.15,
}


def compute_composite(
    results: dict[str, DetectionResult],
    weights: dict[str, float] | None = None,
) -> float:
    """Compute a weighted composite score from individual detector results.

    Returns a value clamped between 0 and 100.
    """
    w = weights or DEFAULT_WEIGHTS

    total = 0.0
    weight_sum = 0.0
    for name, result in results.items():
        detector_weight = w.get(name, 0.0)
        total += result.score * detector_weight
        weight_sum += detector_weight

    # Normalise in case weights don't sum to 1
    if weight_sum > 0:
        score = total / weight_sum
    else:
        score = 0.0

    return round(max(0.0, min(score, 100.0)), 2)
