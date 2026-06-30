"""Model promotion: shadow -> challenger -> canary, with safety gates (ML-21).

Blueprint Part 18 / Part 31 model-CD pipeline:

* **shadow scoring** — a challenger scores the same live traffic as the champion but
  raises NO alerts; promotion is GATED on the challenger *beating the champion in shadow*
  (on an honest, time-split eval metric — AUPRC by default).
* **signature verification on load** — a model whose live feature schema does not hash
  to its registered signature is REJECTED (a serving/feature-contract drift guard).
* **canary** — after promotion, route a small traffic fraction to the new champion and
  watch its live metric.
* **automatic rollback on metric regression** — if the canary/monitored metric regresses
  past a tolerance versus the prior champion, roll back automatically.

ALERT-ONLY + HONEST EVAL: shadow and canary never auto-block anyone, and the gating
metric is computed on a held-out time split (never point-adjusted). No heavy model
library is imported here, so this loads in any process.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import numpy as np

from ml.eval.metrics import average_precision
from ml.mlops.registry import ModelRecord, ModelRegistry, model_signature

# A challenger must beat the champion by at least this absolute margin in shadow to promote.
DEFAULT_SHADOW_MARGIN = 0.0
# Auto-rollback if the new champion's live metric drops more than this below the prior one.
DEFAULT_ROLLBACK_TOLERANCE = 0.02


class SignatureError(ValueError):
    """Raised when a model's live feature schema does not match its registered signature."""


def verify_signature(record: ModelRecord, feature_names: Any) -> bool:
    """True iff ``feature_names`` hashes to ``record.signature`` (the registered contract)."""
    expected = record.signature
    if not expected:
        return False
    actual = model_signature(feature_names, model_version=record.model_version)
    return actual == expected


def load_verified(
    registry: ModelRegistry,
    name: str,
    version: str,
    feature_names: Any,
) -> ModelRecord:
    """Load a registered model version only if its signature verifies; else reject.

    Returns the :class:`ModelRecord` (the artefact bytes live in the ``ModelStore`` it
    points at). Raises :class:`SignatureError` on a bad/mismatched signature.
    """
    rec = registry.get(name, version)
    if rec is None:
        raise KeyError(f"{name}@{version} is not registered")
    if not verify_signature(rec, feature_names):
        raise SignatureError(
            f"signature mismatch loading {rec.model_version}: live feature schema does not "
            f"match the registered signature {rec.signature!r}. Refusing to load."
        )
    return rec


@dataclass
class ShadowResult:
    """Outcome of shadow-scoring a challenger against the champion."""

    champion_metric: float
    challenger_metric: float
    margin: float
    beats_champion: bool
    metric_name: str = "average_precision"
    n: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "champion_metric": round(self.champion_metric, 6),
            "challenger_metric": round(self.challenger_metric, 6),
            "margin": round(self.margin, 6),
            "beats_champion": self.beats_champion,
            "metric_name": self.metric_name,
            "n": self.n,
        }


def _proba(model: Any, X: Any) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(X)
    elif hasattr(model, "score_samples"):
        p = model.score_samples(X)
    elif callable(model):
        p = model(X)
    else:
        raise TypeError("model must expose predict_proba/score_samples or be callable")
    p = np.asarray(p, dtype=float)
    if p.ndim == 2 and p.shape[1] == 2:  # sklearn-style (n,2) -> positive-class column
        p = p[:, 1]
    return p.ravel()


def shadow_evaluate(
    champion: Any,
    challenger: Any,
    X_shadow: Any,
    y_shadow: Any,
    *,
    margin: float = DEFAULT_SHADOW_MARGIN,
    metric: Callable[[Any, Any], float] = average_precision,
    metric_name: str = "average_precision",
) -> ShadowResult:
    """Score both models on the SAME held-out shadow traffic; challenger must beat champion.

    Honest eval: ``X_shadow``/``y_shadow`` must be a time-split future slice (the caller
    owns the split). The challenger only "wins" if it beats the champion by ``margin``.
    """
    y = np.asarray(list(y_shadow))
    champ_m = float(metric(y, _proba(champion, X_shadow)))
    chal_m = float(metric(y, _proba(challenger, X_shadow)))
    diff = chal_m - champ_m
    return ShadowResult(
        champion_metric=champ_m,
        challenger_metric=chal_m,
        margin=diff,
        beats_champion=bool(np.isfinite(diff) and diff > margin),
        metric_name=metric_name,
        n=int(len(y)),
    )


@dataclass
class CanaryResult:
    """Outcome of a canary deployment of the new champion."""

    prior_metric: float
    canary_metric: float
    regression: float
    rolled_back: bool
    tolerance: float
    rolled_back_to: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prior_metric": round(self.prior_metric, 6),
            "canary_metric": round(self.canary_metric, 6),
            "regression": round(self.regression, 6),
            "rolled_back": self.rolled_back,
            "tolerance": self.tolerance,
            "rolled_back_to": self.rolled_back_to,
        }


@dataclass
class PromotionDecision:
    """The full audit trail of a promotion attempt (shadow -> promote -> canary/rollback)."""

    name: str
    challenger_version: str
    promoted: bool
    shadow: ShadowResult
    signature_ok: bool
    canary: Optional[CanaryResult] = None
    champion_version: Optional[str] = None
    reason: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "challenger_version": self.challenger_version,
            "champion_version": self.champion_version,
            "promoted": self.promoted,
            "signature_ok": self.signature_ok,
            "shadow": self.shadow.to_dict(),
            "canary": self.canary.to_dict() if self.canary else None,
            "reason": self.reason,
            "ts": self.ts,
        }


class PromotionManager:
    """Drives the gated promotion pipeline against a :class:`ModelRegistry`.

    Usage::

        mgr = PromotionManager(registry)
        decision = mgr.evaluate_and_promote(
            name, challenger_version, challenger_model, champion_model,
            X_shadow, y_shadow, feature_names,
        )

    A challenger promotes only if (1) its signature verifies on load, AND (2) it beats the
    champion in shadow. After promotion an optional canary can trigger auto-rollback.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        shadow_margin: float = DEFAULT_SHADOW_MARGIN,
        rollback_tolerance: float = DEFAULT_ROLLBACK_TOLERANCE,
    ) -> None:
        self.registry = registry
        self.shadow_margin = shadow_margin
        self.rollback_tolerance = rollback_tolerance

    def evaluate_and_promote(
        self,
        name: str,
        challenger_version: str,
        challenger_model: Any,
        champion_model: Any,
        X_shadow: Any,
        y_shadow: Any,
        feature_names: Any,
        *,
        reviewer: Optional[str] = None,
        metric: Callable[[Any, Any], float] = average_precision,
    ) -> PromotionDecision:
        """Verify signature + shadow-evaluate; promote the challenger only if it wins."""
        champ_rec = self.registry.champion(name)
        # (1) signature verification on load of the challenger.
        chal_rec = self.registry.get(name, challenger_version)
        sig_ok = chal_rec is not None and verify_signature(chal_rec, feature_names)

        shadow = shadow_evaluate(
            champion_model,
            challenger_model,
            X_shadow,
            y_shadow,
            margin=self.shadow_margin,
            metric=metric,
        )

        if not sig_ok:
            return PromotionDecision(
                name=name,
                challenger_version=challenger_version,
                champion_version=champ_rec.version if champ_rec else None,
                promoted=False,
                shadow=shadow,
                signature_ok=False,
                reason="signature verification failed on load; challenger rejected",
            )
        if not shadow.beats_champion:
            return PromotionDecision(
                name=name,
                challenger_version=challenger_version,
                champion_version=champ_rec.version if champ_rec else None,
                promoted=False,
                shadow=shadow,
                signature_ok=True,
                reason=(
                    f"challenger did not beat champion in shadow "
                    f"({shadow.challenger_metric:.4f} <= {shadow.champion_metric:.4f} + margin)"
                ),
            )

        self.registry.promote(name, challenger_version, reviewer=reviewer)
        return PromotionDecision(
            name=name,
            challenger_version=challenger_version,
            champion_version=challenger_version,
            promoted=True,
            shadow=shadow,
            signature_ok=True,
            reason="challenger beat champion in shadow + signature verified -> promoted",
        )

    def canary(
        self,
        name: str,
        new_champion_model: Any,
        prior_champion_model: Any,
        X_live: Any,
        y_live: Any,
        *,
        prior_version: Optional[str] = None,
        metric: Callable[[Any, Any], float] = average_precision,
    ) -> CanaryResult:
        """Watch the new champion's live metric; auto-rollback on a regression.

        If the new champion's live metric drops more than ``rollback_tolerance`` below the
        prior champion's, the prior champion is re-promoted (rollback) automatically.
        """
        y = np.asarray(list(y_live))
        prior_m = float(metric(y, _proba(prior_champion_model, X_live)))
        new_m = float(metric(y, _proba(new_champion_model, X_live)))
        regression = prior_m - new_m
        rolled_back = bool(
            np.isfinite(regression) and regression > self.rollback_tolerance
        )
        rolled_to = None
        if rolled_back and prior_version is not None:
            self.registry.promote(name, prior_version, reviewer="auto-rollback")
            rolled_to = prior_version
        return CanaryResult(
            prior_metric=prior_m,
            canary_metric=new_m,
            regression=regression,
            rolled_back=rolled_back,
            tolerance=self.rollback_tolerance,
            rolled_back_to=rolled_to,
        )


__all__ = [
    "DEFAULT_SHADOW_MARGIN",
    "DEFAULT_ROLLBACK_TOLERANCE",
    "SignatureError",
    "verify_signature",
    "load_verified",
    "ShadowResult",
    "shadow_evaluate",
    "CanaryResult",
    "PromotionDecision",
    "PromotionManager",
]
