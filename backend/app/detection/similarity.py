from __future__ import annotations

import asyncio
import functools
import threading
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .base import BaseDetector, DetectionResult

_model_lock = threading.Lock()
_model_instance = None


def _get_model():
    """Lazy singleton loader for the sentence-transformers model."""
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                from sentence_transformers import SentenceTransformer

                _model_instance = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_instance


def _compute_similarity(outputs: list[str], threshold: float) -> DetectionResult:
    """Run similarity computation synchronously (CPU-bound)."""
    model = _get_model()
    embeddings = model.encode(outputs, convert_to_numpy=True)

    sim_matrix = cosine_similarity(embeddings)

    n = len(outputs)
    pairs: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(float(sim_matrix[i][j]))

    mean_sim = float(np.mean(pairs)) if pairs else 0.0
    score = round(mean_sim * 100, 2)

    flag = "semantic_loop" if score > threshold else None
    detail = f"Mean pairwise similarity {mean_sim:.3f} across {len(outputs)} outputs"

    return DetectionResult(
        score=score,
        flag=flag,
        detail=detail,
        metadata={
            "embeddings": embeddings.tolist(),
            "pairwise_similarities": pairs,
            "mean_similarity": mean_sim,
        },
    )


class SimilarityDetector(BaseDetector):
    name = "similarity"
    default_weight = 0.20

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        threshold = thresholds.get("similarity", 85)
        window = 3

        outputs: list[str] = []
        for step in steps[-window:]:
            text = (step.get("output_text") or "").strip()
            if text:
                outputs.append(text)

        if len(outputs) < 2:
            return DetectionResult(score=0.0, detail="Not enough outputs to compare")

        # Run CPU-bound model inference in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(_compute_similarity, outputs, threshold)
        )
