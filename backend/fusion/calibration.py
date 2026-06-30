"""Calibration to 0–100 + severity × confidence (BACKEND-12, blueprint Part 18.1 l.572).

# STUB: ML (isotonic/Platt calibrator). A monotone, well-behaved mapping from a fused probability
to a calibrated 0–100 risk score, plus severity bands and a confidence derived from cross-layer
agreement. Swapping ML's fitted calibrator in changes only ``calibrate_probability``.
"""

from __future__ import annotations

import math

HIGH_THRESHOLD = 70
MEDIUM_THRESHOLD = 40


def calibrate_probability(prob: float) -> int:
    """Map a fused probability (0–1) to a calibrated 0–100 integer risk score."""
    prob = max(0.0, min(1.0, prob))
    return int(round(prob * 100))


def severity_for(score_0_100: int, hard_hit: bool = False) -> str:
    if hard_hit or score_0_100 >= HIGH_THRESHOLD:
        return "high"
    if score_0_100 >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def confidence_from(layer_scores: list[float], prob: float) -> float:
    """Confidence = cross-layer agreement (low dispersion ⇒ high confidence), blended with prob."""
    if layer_scores:
        mean = sum(layer_scores) / len(layer_scores)
        var = sum((s - mean) ** 2 for s in layer_scores) / len(layer_scores)
        agreement = 1.0 - min(1.0, math.sqrt(var) * 2)  # tighter spread ⇒ higher agreement
    else:
        agreement = 0.5
    conf = 0.5 * agreement + 0.5 * prob
    return round(max(0.0, min(0.99, conf)), 2)
