from __future__ import annotations

import asyncio
import functools
import logging
import threading
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .base import BaseDetector, DetectionResult

logger = logging.getLogger(__name__)

_model_lock = threading.Lock()
_model_instance = None
_use_transformer = None  # tri-state: None=unknown, True=available, False=fallback


def _check_transformer_available() -> bool:
    """Check if sentence-transformers is installed and usable."""
    global _use_transformer
    if _use_transformer is not None:
        return _use_transformer
    try:
        import sentence_transformers  # noqa: F401
        _use_transformer = True
    except ImportError:
        _use_transformer = False
        logger.info("sentence-transformers not available — using TF-IDF fallback (lightweight mode)")
    return _use_transformer


def _get_model():
    """Lazy singleton loader for the sentence-transformers model."""
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                from sentence_transformers import SentenceTransformer
                _model_instance = SentenceTransformer("all-MiniLM-L6-v2")
    return _model_instance


def _compute_similarity_transformer(outputs: list[str], threshold: float) -> DetectionResult:
    """Compute similarity using sentence-transformers (high accuracy, GPU/CPU heavy)."""
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
    detail = f"Mean pairwise similarity {mean_sim:.3f} across {len(outputs)} outputs (transformer)"

    return DetectionResult(
        score=score,
        flag=flag,
        detail=detail,
        metadata={
            "embeddings": embeddings.tolist(),
            "pairwise_similarities": pairs,
            "mean_similarity": mean_sim,
            "engine": "sentence-transformers",
        },
    )


def _compute_similarity_tfidf(outputs: list[str], threshold: float) -> DetectionResult:
    """Compute similarity using TF-IDF + cosine (lightweight, no GPU needed).

    This fallback uses scikit-learn's TfidfVectorizer which produces surprisingly
    good results for detecting repetitive agent outputs — because repeated outputs
    share nearly identical token distributions.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),  # unigrams + bigrams + trigrams for better semantic capture
        sublinear_tf=True,
    )
    tfidf_matrix = vectorizer.fit_transform(outputs)
    sim_matrix = cosine_similarity(tfidf_matrix)

    n = len(outputs)
    pairs: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append(float(sim_matrix[i][j]))

    mean_sim = float(np.mean(pairs)) if pairs else 0.0
    score = round(mean_sim * 100, 2)

    flag = "semantic_loop" if score > threshold else None
    detail = f"Mean pairwise similarity {mean_sim:.3f} across {len(outputs)} outputs (tfidf)"

    return DetectionResult(
        score=score,
        flag=flag,
        detail=detail,
        metadata={
            "pairwise_similarities": pairs,
            "mean_similarity": mean_sim,
            "engine": "tfidf-ngram",
        },
    )


def _compute_similarity(outputs: list[str], threshold: float) -> DetectionResult:
    """Auto-select best available similarity engine."""
    if _check_transformer_available():
        return _compute_similarity_transformer(outputs, threshold)
    return _compute_similarity_tfidf(outputs, threshold)


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
