"""Core ML interfaces and score/reason-code/alert contracts (ML-1)."""
from __future__ import annotations

from ml.base.interfaces import (
    Alert,
    BaseDetector,
    BaseModel,
    BaseScorer,
    ReasonCode,
    REASON_SOURCES,
    ScoreResult,
    Severity,
    feature_names_of,
    normalize_scores,
    severity_from_score,
)

__all__ = [
    "Alert",
    "BaseDetector",
    "BaseModel",
    "BaseScorer",
    "ReasonCode",
    "REASON_SOURCES",
    "ScoreResult",
    "Severity",
    "feature_names_of",
    "normalize_scores",
    "severity_from_score",
]
