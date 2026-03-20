"""Token Entropy Analyzer -- information-theoretic analysis of agent outputs.

This detector operates at the information theory level, measuring the actual
*information content* of agent outputs rather than their semantic meaning.
It is complementary to embedding-based detectors:

- **Embedding detectors** (Similarity, Goal Drift): Measure *what* the agent
  is saying and whether it's repeating meaning.
- **Entropy detector**: Measures *how much information* each output carries,
  regardless of topic.

A productive agent produces outputs with high information density -- each
token contributes new information. A looping or stalling agent produces
predictable, compressible output -- the same patterns repeat, entropy drops,
and compression ratio increases.

Algorithm:

1. **Shannon Entropy (Character-Level)**:
   Computes H = -sum(p(c) * log2(p(c))) for each character c in the output.
   Normalized by log2(alphabet_size) to produce a value in [0, 1].
   - H ~ 1.0: Maximum entropy -- every character equally likely (random noise)
   - H ~ 0.7-0.9: Natural language (typical for English prose)
   - H < 0.5: Highly repetitive or templated text

2. **Shannon Entropy (Word-Level)**:
   Same formula but applied to word tokens. More sensitive to semantic
   repetition than character-level entropy. Captures cases where the agent
   uses different characters but repeats the same words/phrases.
   - H_word / log2(vocab_size): Normalized word entropy
   - Declining word entropy across steps = vocabulary is shrinking

3. **Compression Ratio (zlib)**:
   Compresses each output with zlib and measures:
   ratio = len(compressed) / len(original)
   - ratio ~ 0.3-0.5: Normal for English text
   - ratio < 0.2: Highly repetitive content (compresses very well)
   - ratio > 0.7: High-entropy content (random or very diverse)

   Also computes the *cross-step compression ratio*: concatenate all recent
   outputs and compress as a single block. If the cross-step ratio is much
   lower than individual ratios, the outputs share a lot of structure
   (inter-step repetition that single-step analysis misses).

4. **Entropy Gradient**:
   Tracks how each metric changes over time. Computed as the slope of a
   linear regression over the last N steps:
   - Negative char_entropy slope = outputs becoming more predictable
   - Negative word_entropy slope = vocabulary shrinking
   - Negative compression_ratio slope = outputs becoming more compressible
   - All three declining together = strong "entropy collapse" signal

Scoring:
- low_entropy: up to 30 points (current entropy below natural language baseline)
- high_compression: up to 25 points (cross-step compression anomaly)
- declining_gradient: up to 25 points (entropy trend over time)
- vocabulary_contraction: up to 20 points (word entropy decline)

Flag: "entropy_collapse" when composite score exceeds threshold.
"""

from __future__ import annotations

import math
import re
import zlib
from collections import Counter
from typing import Any

from .base import BaseDetector, DetectionResult


# ---------------------------------------------------------------------------
# Core information-theoretic functions
# ---------------------------------------------------------------------------

def _shannon_entropy_chars(text: str) -> float:
    """Compute normalized Shannon entropy at the character level.

    Returns a value in [0, 1] where 1.0 = maximum entropy.
    Uses base-2 logarithm (bits) and normalizes by log2 of the
    number of unique characters observed.

    For an empty string, returns 0.0.
    """
    if not text:
        return 0.0

    freq = Counter(text)
    total = len(text)
    alphabet_size = len(freq)

    if alphabet_size <= 1:
        return 0.0

    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    # Normalize by maximum possible entropy for this alphabet
    max_entropy = math.log2(alphabet_size)
    return entropy / max_entropy if max_entropy > 0 else 0.0


def _shannon_entropy_words(text: str) -> tuple[float, int]:
    """Compute normalized Shannon entropy at the word level.

    Returns (normalized_entropy, vocabulary_size).
    Tokenizes on word boundaries, lowercased.
    """
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) <= 1:
        return 0.0, len(set(tokens))

    freq = Counter(tokens)
    total = len(tokens)
    vocab_size = len(freq)

    if vocab_size <= 1:
        return 0.0, vocab_size

    entropy = 0.0
    for count in freq.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    max_entropy = math.log2(vocab_size)
    normalized = entropy / max_entropy if max_entropy > 0 else 0.0
    return normalized, vocab_size


def _compression_ratio(text: str) -> float:
    """Compute the zlib compression ratio for a text string.

    Returns len(compressed) / len(original).
    A lower ratio means more repetitive/compressible content.

    Uses zlib level 6 (default) for consistent results.
    Returns 1.0 for empty strings.
    """
    if not text:
        return 1.0

    original_bytes = text.encode("utf-8")
    compressed = zlib.compress(original_bytes, 6)

    return len(compressed) / len(original_bytes)


def _cross_step_compression_ratio(outputs: list[str]) -> float:
    """Compute compression ratio of all outputs concatenated.

    If this ratio is significantly lower than the average of individual
    ratios, the outputs share substantial structure across steps.

    Uses a separator to prevent cross-boundary artifacts.
    """
    if not outputs:
        return 1.0

    concatenated = "\n---STEP_BOUNDARY---\n".join(outputs)
    return _compression_ratio(concatenated)


def _linear_slope(values: list[float]) -> float:
    """Compute the slope of a linear regression over a sequence.

    Returns the slope (change per step). Negative = declining trend.
    """
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    return numerator / denominator if denominator > 0 else 0.0


# ---------------------------------------------------------------------------
# Natural language baselines
# ---------------------------------------------------------------------------

# Empirical baselines for English prose (from analysis of diverse corpora).
# These serve as reference points -- outputs significantly below these
# values are unusually repetitive.
_CHAR_ENTROPY_BASELINE = 0.75  # Typical English character entropy (normalized)
_WORD_ENTROPY_BASELINE = 0.85  # Typical English word entropy (normalized)
_COMPRESSION_BASELINE = 0.38   # Typical zlib ratio for English text


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

class TokenEntropyAnalyzer(BaseDetector):
    """Measures information density of agent outputs using Shannon entropy,
    compression analysis, and trend detection.

    Identifies "entropy collapse" -- the information-theoretic signature
    of an agent producing increasingly predictable, repetitive output.
    """

    name = "token_entropy"
    default_weight = 0.10

    async def analyze(
        self, steps: list[dict[str, Any]], thresholds: dict | None = None
    ) -> DetectionResult:
        thresholds = thresholds or {}
        window = thresholds.get("token_entropy_window", 6)

        recent_steps = steps[-window:]
        outputs: list[str] = []
        for step in recent_steps:
            text = (step.get("output_text") or "").strip()
            if text:
                outputs.append(text)

        if len(outputs) < 2:
            return DetectionResult(
                score=0.0,
                detail="Not enough outputs for entropy analysis",
            )

        # ----- Phase 1: Per-step entropy metrics -----
        char_entropies: list[float] = []
        word_entropies: list[float] = []
        vocab_sizes: list[int] = []
        compression_ratios: list[float] = []

        for output in outputs:
            ce = _shannon_entropy_chars(output)
            we, vs = _shannon_entropy_words(output)
            cr = _compression_ratio(output)

            char_entropies.append(ce)
            word_entropies.append(we)
            vocab_sizes.append(vs)
            compression_ratios.append(cr)

        # ----- Phase 2: Cross-step compression -----
        cross_ratio = _cross_step_compression_ratio(outputs)
        avg_individual_ratio = (
            sum(compression_ratios) / len(compression_ratios)
        )
        # Cross-step anomaly: how much MORE compressible is the concatenation
        # compared to individual outputs? A big drop means inter-step repetition.
        compression_anomaly = max(0.0, avg_individual_ratio - cross_ratio)

        # ----- Phase 3: Entropy gradients (trends over time) -----
        char_entropy_slope = _linear_slope(char_entropies)
        word_entropy_slope = _linear_slope(word_entropies)
        compression_slope = _linear_slope(compression_ratios)
        vocab_slope = _linear_slope([float(v) for v in vocab_sizes])

        # ----- Phase 4: Current values vs baselines -----
        current_char_entropy = char_entropies[-1]
        current_word_entropy = word_entropies[-1]
        current_compression = compression_ratios[-1]

        # ----- Score computation -----

        # Component 1: Low entropy (current output below baseline)
        low_entropy_score = 0.0
        char_deficit = max(0.0, _CHAR_ENTROPY_BASELINE - current_char_entropy)
        word_deficit = max(0.0, _WORD_ENTROPY_BASELINE - current_word_entropy)
        low_entropy_score = (char_deficit * 20 + word_deficit * 20)
        low_entropy_score = min(low_entropy_score, 30.0)

        # Component 2: High compression (cross-step anomaly)
        compression_score = 0.0
        if compression_anomaly > 0.05:
            compression_score = min(compression_anomaly * 200, 25.0)
        # Also penalize if individual compression is very low
        if current_compression < 0.25:
            compression_score += 10.0
        compression_score = min(compression_score, 25.0)

        # Component 3: Declining gradient (negative slopes)
        gradient_score = 0.0
        if char_entropy_slope < -0.01:
            gradient_score += min(abs(char_entropy_slope) * 200, 12.0)
        if word_entropy_slope < -0.01:
            gradient_score += min(abs(word_entropy_slope) * 200, 13.0)
        gradient_score = min(gradient_score, 25.0)

        # Component 4: Vocabulary contraction
        vocab_score = 0.0
        if vocab_slope < -1.0:  # Losing more than 1 unique word per step
            vocab_score = min(abs(vocab_slope) * 5, 20.0)
        vocab_score = min(vocab_score, 20.0)

        score = low_entropy_score + compression_score + gradient_score + vocab_score
        score = round(min(score, 100.0), 2)

        flag_threshold = thresholds.get("token_entropy", 35)
        flag = "entropy_collapse" if score >= flag_threshold else None

        detail_parts = []
        if low_entropy_score > 5:
            detail_parts.append(
                f"low entropy (char: {current_char_entropy:.3f}, "
                f"word: {current_word_entropy:.3f})"
            )
        if compression_score > 5:
            detail_parts.append(
                f"high compressibility (cross-step anomaly: {compression_anomaly:.3f})"
            )
        if gradient_score > 5:
            detail_parts.append(
                f"declining entropy gradient "
                f"(char slope: {char_entropy_slope:.4f}, "
                f"word slope: {word_entropy_slope:.4f})"
            )
        if vocab_score > 5:
            detail_parts.append(f"vocabulary contracting (slope: {vocab_slope:.1f})")

        detail = "; ".join(detail_parts) if detail_parts else "Entropy levels normal"

        return DetectionResult(
            score=score,
            flag=flag,
            detail=detail,
            metadata={
                "char_entropies": char_entropies,
                "word_entropies": word_entropies,
                "vocab_sizes": vocab_sizes,
                "compression_ratios": compression_ratios,
                "cross_step_compression": cross_ratio,
                "compression_anomaly": compression_anomaly,
                "char_entropy_slope": char_entropy_slope,
                "word_entropy_slope": word_entropy_slope,
                "compression_slope": compression_slope,
                "vocab_slope": vocab_slope,
                "current_char_entropy": current_char_entropy,
                "current_word_entropy": current_word_entropy,
                "current_compression": current_compression,
            },
        )
