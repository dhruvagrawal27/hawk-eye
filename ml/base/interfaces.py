"""Core ML interfaces and the score/reason-code/alert contracts (ML-1).

These are the contracts every layer (L2-L6) and the serving handoff integrate against.
The reason-code and alert shapes mirror ``BACKEND.md`` §2 exactly (BACKEND owns the
contract; we produce payloads that match it).

* ``ReasonCode``  -> {source, code|feature, detail|contribution}
* ``Alert``       -> the L6 alert JSON (BACKEND.md §2)
* ``ScoreResult`` -> a single per-layer per-entity score in [0,1] + reason codes
* ``BaseDetector``-> unsupervised layers (L2, L4-unsupervised): score_samples -> [0,1]
* ``BaseScorer``  -> supervised layers (L3, L5, L6): predict_proba -> [0,1]
"""

from __future__ import annotations

import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

import numpy as np

try:  # joblib ships with scikit-learn; fall back to pickle if somehow absent
    import joblib

    _dump, _load = joblib.dump, joblib.load
except Exception:  # pragma: no cover

    def _dump(obj: Any, path: str) -> None:
        with open(path, "wb") as fh:
            pickle.dump(obj, fh)

    def _load(path: str) -> Any:
        with open(path, "rb") as fh:
            return pickle.load(fh)


# --------------------------------------------------------------------------- #
# Reason codes (BACKEND.md §2 shape)                                           #
# --------------------------------------------------------------------------- #
REASON_SOURCES = ("rule", "shap", "graph", "attention")


@dataclass
class ReasonCode:
    """A single piece of alert provenance. Matches BACKEND.md §2.

    Only the fields relevant to the ``source`` are emitted by ``to_dict`` (None dropped):
    rule -> code/detail; shap -> feature/contribution; graph -> detail;
    attention -> feature/detail/contribution.
    """

    source: str
    code: Optional[str] = None
    feature: Optional[str] = None
    detail: Optional[str] = None
    contribution: Optional[float] = None

    def __post_init__(self) -> None:
        if self.source not in REASON_SOURCES:
            raise ValueError(
                f"reason source must be one of {REASON_SOURCES}, got {self.source!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"source": self.source}
        if self.code is not None:
            out["code"] = self.code
        if self.feature is not None:
            out["feature"] = self.feature
        if self.detail is not None:
            out["detail"] = self.detail
        if self.contribution is not None:
            out["contribution"] = round(float(self.contribution), 4)
        return out


class Severity(str, Enum):
    # The wire contract (BACKEND.md §2) is exactly {low, medium, high} — alerts that leave the
    # perimeter MUST use one of these so BACKEND's Severity enum never rejects an ML alert.
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def severity_from_score(risk_score: float) -> Severity:
    """Map a 0-100 calibrated risk score to a severity band (BACKEND.md §2: low|medium|high).

    Bands chosen so the BACKEND.md §2 worked example (risk_score 87 -> 'high') holds. There is
    intentionally NO 'critical' band — the contract is three levels; intensity above 'high' is
    carried by the calibrated risk_score (0-100) + confidence, not a 4th severity label.
    """
    if risk_score >= 70:
        return Severity.HIGH
    if risk_score >= 40:
        return Severity.MEDIUM
    return Severity.LOW


@dataclass
class Alert:
    """The L6 alert output (BACKEND.md §2). Produced by L6 fusion (ML-7)."""

    alert_id: str
    entity_id: str
    risk_score: int
    severity: str
    confidence: float
    status: str = "open"
    created_ts: Optional[str] = None
    contributing_layers: list[str] = field(default_factory=list)
    reason_codes: list[ReasonCode] = field(default_factory=list)
    exposure_inr: Optional[int] = None
    sla_due_ts: Optional[str] = None
    pii_tokenized: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "entity_id": self.entity_id,
            "risk_score": int(self.risk_score),
            "severity": self.severity,
            "confidence": round(float(self.confidence), 4),
            "status": self.status,
            "created_ts": self.created_ts,
            "contributing_layers": list(self.contributing_layers),
            "reason_codes": [rc.to_dict() for rc in self.reason_codes],
            "exposure_inr": self.exposure_inr,
            "sla_due_ts": self.sla_due_ts,
            "pii_tokenized": self.pii_tokenized,
        }


@dataclass
class ScoreResult:
    """A single per-layer per-entity score in [0,1] plus reason codes and provenance."""

    entity_id: str
    score: float
    layer: str
    model_version: str
    reason_codes: list[ReasonCode] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "score": round(float(self.score), 6),
            "layer": self.layer,
            "model_version": self.model_version,
            "reason_codes": [rc.to_dict() for rc in self.reason_codes],
            "extra": self.extra,
        }


# --------------------------------------------------------------------------- #
# Score normalisation helpers (raw anomaly scores -> [0,1])                    #
# --------------------------------------------------------------------------- #
def normalize_scores(scores: np.ndarray, method: str = "rank") -> np.ndarray:
    """Map arbitrary real-valued anomaly scores to [0,1] (higher = more anomalous)."""
    s = np.asarray(scores, dtype=float).ravel()
    if s.size == 0:
        return s
    if method == "rank":
        order = s.argsort().argsort().astype(float)
        denom = max(s.size - 1, 1)
        return order / denom
    if method == "minmax":
        lo, hi = float(np.nanmin(s)), float(np.nanmax(s))
        if hi - lo < 1e-12:
            return np.full_like(s, 0.5)
        return (s - lo) / (hi - lo)
    if method == "sigmoid":
        mu, sigma = float(np.nanmean(s)), float(np.nanstd(s)) or 1.0
        return 1.0 / (1.0 + np.exp(-(s - mu) / sigma))
    raise ValueError(f"unknown normalize method {method!r}")


# --------------------------------------------------------------------------- #
# Model base classes                                                          #
# --------------------------------------------------------------------------- #
class BaseModel(ABC):
    """Common base for all detectors/scorers: identity, fit, persistence."""

    layer: str = "L0"

    def __init__(self, name: str, version: str = "0.1.0") -> None:
        self.name = name
        self.version = version
        self._fitted = False

    @property
    def model_version(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @abstractmethod
    def fit(self, X: Any, y: Optional[Any] = None) -> "BaseModel": ...

    def save(self, path: str) -> str:
        _dump(self, path)
        return path

    @staticmethod
    def load(path: str) -> "BaseModel":
        return _load(path)


class BaseDetector(BaseModel):
    """Unsupervised detector (L2, L4-unsupervised). ``score_samples`` returns [0,1]."""

    layer = "L2"

    @abstractmethod
    def score_samples(self, X: Any) -> np.ndarray:
        """Return per-row anomaly scores in [0,1] (higher = more anomalous)."""

    def explain(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Per-row reason codes. Default: none (override for per-feature explanations)."""
        n = len(X)
        return [[] for _ in range(n)]


class BaseScorer(BaseModel):
    """Supervised scorer (L3, L5, L6). ``predict_proba`` returns calibrated [0,1]."""

    layer = "L3"

    @abstractmethod
    def predict_proba(self, X: Any) -> np.ndarray:
        """Return per-row P(fraud) in [0,1]."""

    def reason_codes(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Per-row reason codes. Default: none (override with TreeSHAP/attention/graph)."""
        n = len(X)
        return [[] for _ in range(n)]


def feature_names_of(X: Any) -> list[str]:
    """Best-effort feature-name extraction for explanations."""
    cols = getattr(X, "columns", None)
    if cols is not None:
        return [str(c) for c in cols]
    width = np.asarray(X).shape[1] if np.asarray(X).ndim == 2 else 0
    return [f"f{i}" for i in range(width)]


def as_sequence(x: Any) -> Sequence[Any]:
    return list(x)
