"""Ongoing model monitoring (ML-23; blueprint Part 27).

Continuous post-deployment monitoring of a model across the four MRM dimensions:

* **drift**     — data drift (PSI/KS, via :mod:`ml.mlops.drift`),
* **decay**     — concept drift: rolling precision/recall over dispositions,
* **stability** — score-distribution stability between reference and current windows,
* **outcome analysis** — predicted risk vs *realized* fraud (do high-risk alerts actually
  confirm as fraud, and is recall on realized fraud holding up).

Produces a consolidated health report + a retrain recommendation (reusing the ML-22
:class:`RetrainTrigger`). ALERT-ONLY + HONEST EVAL throughout. No heavy model library is
imported, so this loads in any process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ml.mlops.drift import (
    ConceptDriftReport,
    DataDriftReport,
    RetrainTrigger,
    data_drift_report,
    population_stability_index,
    rolling_precision_recall,
)


@dataclass
class StabilityReport:
    """Score-distribution stability between a reference and current window (PSI on scores)."""

    score_psi: float
    stable: bool

    def to_dict(self) -> dict[str, Any]:
        return {"score_psi": round(self.score_psi, 6), "stable": self.stable}


@dataclass
class OutcomeAnalysis:
    """Predicted risk vs realized fraud (does the model's risk track real outcomes?)."""

    n: int
    realized_fraud_rate: float
    precision_at_alert_threshold: float
    recall_on_realized_fraud: float
    high_risk_confirmation_rate: float
    alert_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "realized_fraud_rate": round(self.realized_fraud_rate, 4),
            "precision_at_alert_threshold": round(self.precision_at_alert_threshold, 4),
            "recall_on_realized_fraud": round(self.recall_on_realized_fraud, 4),
            "high_risk_confirmation_rate": round(self.high_risk_confirmation_rate, 4),
            "alert_threshold": self.alert_threshold,
        }


def outcome_analysis(
    realized_fraud: Iterable[Any],
    risk_scores: Iterable[float],
    *,
    alert_threshold: float = 0.5,
    high_risk_quantile: float = 0.9,
) -> OutcomeAnalysis:
    """Compare predicted risk to realized fraud outcomes (Part 27 outcome analysis)."""
    y = (np.asarray(list(realized_fraud), dtype=float) >= 0.5).astype(int)
    s = np.asarray(list(risk_scores), dtype=float)
    n = len(y)
    if n == 0:
        return OutcomeAnalysis(0, 0.0, 0.0, 0.0, 0.0, alert_threshold)
    flagged = s >= alert_threshold
    tp = float(np.sum(flagged & (y == 1)))
    fp = float(np.sum(flagged & (y == 0)))
    fn = float(np.sum(~flagged & (y == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    hi_cut = float(np.quantile(s, high_risk_quantile)) if s.size else alert_threshold
    hi_mask = s >= hi_cut
    hi_conf = float(y[hi_mask].mean()) if hi_mask.any() else 0.0
    return OutcomeAnalysis(
        n=n,
        realized_fraud_rate=float(y.mean()),
        precision_at_alert_threshold=precision,
        recall_on_realized_fraud=recall,
        high_risk_confirmation_rate=hi_conf,
        alert_threshold=alert_threshold,
    )


def score_stability(
    reference_scores: Iterable[float], current_scores: Iterable[float], *, threshold: float = 0.25
) -> StabilityReport:
    """PSI on the SCORE distribution (a stable model keeps a stable output distribution)."""
    psi = population_stability_index(reference_scores, current_scores)
    return StabilityReport(score_psi=psi, stable=psi < threshold)


@dataclass
class MonitoringReport:
    """Consolidated model-health report across drift / decay / stability / outcomes."""

    model_id: str
    data_drift: Optional[dict[str, Any]] = None
    concept_drift: Optional[dict[str, Any]] = None
    stability: Optional[dict[str, Any]] = None
    outcome: Optional[dict[str, Any]] = None
    retrain_recommended: bool = False
    retrain_reasons: list[str] = field(default_factory=list)
    healthy: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "data_drift": self.data_drift,
            "concept_drift": self.concept_drift,
            "stability": self.stability,
            "outcome": self.outcome,
            "retrain_recommended": self.retrain_recommended,
            "retrain_reasons": self.retrain_reasons,
            "healthy": self.healthy,
        }


class ModelMonitor:
    """Run the four-dimension MRM monitoring pass and recommend a retrain when warranted."""

    def __init__(self, model_id: str, *, trigger: Optional[RetrainTrigger] = None) -> None:
        self.model_id = model_id
        self.trigger = trigger or RetrainTrigger()

    def run(
        self,
        *,
        reference_features: Optional[pd.DataFrame] = None,
        current_features: Optional[pd.DataFrame] = None,
        disposition_y_true: Optional[Iterable[Any]] = None,
        disposition_y_pred: Optional[Iterable[Any]] = None,
        reference_scores: Optional[Iterable[float]] = None,
        current_scores: Optional[Iterable[float]] = None,
        realized_fraud: Optional[Iterable[Any]] = None,
        risk_scores: Optional[Iterable[float]] = None,
        rolling_window: int = 50,
        alert_threshold: float = 0.5,
    ) -> MonitoringReport:
        ddr: Optional[DataDriftReport] = None
        cdr: Optional[ConceptDriftReport] = None
        stab: Optional[StabilityReport] = None
        outc: Optional[OutcomeAnalysis] = None

        if reference_features is not None and current_features is not None:
            ddr = data_drift_report(reference_features, current_features)
        if disposition_y_true is not None and disposition_y_pred is not None:
            cdr = rolling_precision_recall(disposition_y_true, disposition_y_pred, window=rolling_window)
        if reference_scores is not None and current_scores is not None:
            stab = score_stability(reference_scores, current_scores)
        if realized_fraud is not None and risk_scores is not None:
            outc = outcome_analysis(realized_fraud, risk_scores, alert_threshold=alert_threshold)

        signal = self.trigger.evaluate(data_drift=ddr, concept_drift=cdr)
        healthy = not signal.triggered and (stab is None or stab.stable)
        return MonitoringReport(
            model_id=self.model_id,
            data_drift=ddr.to_dict() if ddr else None,
            concept_drift=cdr.to_dict() if cdr else None,
            stability=stab.to_dict() if stab else None,
            outcome=outc.to_dict() if outc else None,
            retrain_recommended=signal.triggered,
            retrain_reasons=signal.reasons,
            healthy=healthy,
        )


__all__ = [
    "StabilityReport",
    "OutcomeAnalysis",
    "outcome_analysis",
    "score_stability",
    "MonitoringReport",
    "ModelMonitor",
]
