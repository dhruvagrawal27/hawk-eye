"""Fairness metrics across protected attributes (ML-25; blueprint Part 29).

Computes disparate-impact + group-fairness metrics across the protected attributes
the blueprint enumerates (grade/seniority, age, gender, region/branch, department,
tenure):

* demographic-parity difference  (alert-rate gap across groups)
* equal-opportunity gap           (TPR gap — recall on true fraud across groups)
* equalized-odds gap              (max of TPR + FPR gaps)
* disparate-impact ratio          (min/max group selection rate; <0.8 = 4/5ths breach)

Uses **Fairlearn** (``fairlearn.metrics``) where it fits and falls back to a direct
numpy computation otherwise, so the module imports and runs even without Fairlearn.

Outputs feed ML-24 (MRM model card / fairness section) via :func:`fairness_metrics_dict`,
and every breach carries reason codes + a narrative (ML-29.2) via :func:`fairness_alerts`.

ALERT-ONLY: a disparate-impact breach raises an *alert* (and can GATE a build per Part 31),
it never auto-blocks a person or mutates a score here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import numpy as np
import pandas as pd

from ml._optional import optional_import
from ml.base.interfaces import ReasonCode

# The protected attributes the blueprint (Part 29) requires we measure across.
PROTECTED_ATTRIBUTES = (
    "grade",
    "seniority",
    "age",
    "gender",
    "region",
    "branch",
    "department",
    "tenure",
)

# 4/5ths (80%) rule: disparate-impact ratio below this is a presumptive adverse-impact breach.
DISPARATE_IMPACT_FLOOR = 0.8
# Gap thresholds above which a parity/odds difference is flagged (0..1 scale).
DEFAULT_GAP_THRESHOLD = 0.1


def _as_binary(arr: Iterable[Any]) -> np.ndarray:
    """Coerce predictions/labels to a 0/1 int array (threshold floats at 0.5)."""
    a = np.asarray(list(arr), dtype=float).ravel()
    if a.size and not np.array_equal(a, a.astype(int)):
        a = (a >= 0.5).astype(int)
    return a.astype(int)


def _group_series(sensitive: Iterable[Any], index: Optional[pd.Index] = None) -> pd.Series:
    s = sensitive if isinstance(sensitive, pd.Series) else pd.Series(list(sensitive), index=index)
    return s.astype(str)


# --------------------------------------------------------------------------- #
# Per-group rate primitives (direct; Fairlearn-independent)                    #
# --------------------------------------------------------------------------- #
def selection_rates(y_pred: Iterable[Any], sensitive: Iterable[Any]) -> dict[str, float]:
    """P(flagged=1) within each group — the basis for demographic parity + DI."""
    yp = pd.Series(_as_binary(y_pred))
    grp = _group_series(sensitive, index=yp.index)
    return {str(g): float(yp[grp.values == g].mean()) for g in pd.unique(grp)}


def _rate_where(y_true: np.ndarray, y_pred: np.ndarray, mask: np.ndarray, cond: np.ndarray) -> Optional[float]:
    sel = mask & cond
    if not sel.any():
        return None
    return float(y_pred[sel].mean())


def group_tpr_fpr(
    y_true: Iterable[Any], y_pred: Iterable[Any], sensitive: Iterable[Any]
) -> dict[str, dict[str, Optional[float]]]:
    """Per-group true-positive-rate (recall) and false-positive-rate."""
    yt, yp = _as_binary(y_true), _as_binary(y_pred)
    grp = _group_series(sensitive).to_numpy()
    out: dict[str, dict[str, Optional[float]]] = {}
    for g in pd.unique(grp):
        mask = grp == g
        out[str(g)] = {
            "tpr": _rate_where(yt, yp, mask, yt == 1),
            "fpr": _rate_where(yt, yp, mask, yt == 0),
            "n": int(mask.sum()),
        }
    return out


def _gap(values: Iterable[Optional[float]]) -> float:
    vals = [v for v in values if v is not None and not np.isnan(v)]
    if len(vals) < 2:
        return 0.0
    return float(max(vals) - min(vals))


# --------------------------------------------------------------------------- #
# Top-level metric: one attribute                                             #
# --------------------------------------------------------------------------- #
@dataclass
class FairnessMetric:
    """Fairness metrics for ONE protected attribute."""

    attribute: str
    demographic_parity_difference: float
    disparate_impact_ratio: float
    equal_opportunity_difference: float
    equalized_odds_difference: float
    selection_rates: dict[str, float] = field(default_factory=dict)
    group_rates: dict[str, dict[str, Optional[float]]] = field(default_factory=dict)
    backend: str = "direct"

    @property
    def disparate_impact_breach(self) -> bool:
        return self.disparate_impact_ratio < DISPARATE_IMPACT_FLOOR

    def breaches(self, gap_threshold: float = DEFAULT_GAP_THRESHOLD) -> list[str]:
        out: list[str] = []
        if self.disparate_impact_breach:
            out.append("disparate_impact")
        if self.demographic_parity_difference > gap_threshold:
            out.append("demographic_parity")
        if self.equal_opportunity_difference > gap_threshold:
            out.append("equal_opportunity")
        if self.equalized_odds_difference > gap_threshold:
            out.append("equalized_odds")
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "attribute": self.attribute,
            "demographic_parity_difference": round(self.demographic_parity_difference, 4),
            "disparate_impact_ratio": round(self.disparate_impact_ratio, 4),
            "equal_opportunity_difference": round(self.equal_opportunity_difference, 4),
            "equalized_odds_difference": round(self.equalized_odds_difference, 4),
            "disparate_impact_breach": self.disparate_impact_breach,
            "selection_rates": {k: round(v, 4) for k, v in self.selection_rates.items()},
            "group_rates": self.group_rates,
            "backend": self.backend,
        }


def disparate_impact_ratio(y_pred: Iterable[Any], sensitive: Iterable[Any]) -> float:
    """min/max selection-rate ratio (the 4/5ths-rule statistic). 1.0 = perfectly even."""
    rates = [r for r in selection_rates(y_pred, sensitive).values()]
    rates = [r for r in rates if not np.isnan(r)]
    if not rates:
        return 1.0
    hi = max(rates)
    if hi <= 0:
        return 1.0  # nobody flagged anywhere -> no disparate impact
    return float(min(rates) / hi)


def _fairlearn_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, grp: pd.Series
) -> Optional[dict[str, float]]:
    """Try Fairlearn for DP/EO/EOdds differences; return None if unavailable/unsupported."""
    fl = optional_import("fairlearn")
    if fl is None:
        return None
    try:
        from fairlearn.metrics import (
            demographic_parity_difference,
            equal_opportunity_difference,
            equalized_odds_difference,
        )

        sf = grp.to_numpy()
        out = {
            "dp": float(demographic_parity_difference(y_true, y_pred, sensitive_features=sf)),
            "eodds": float(equalized_odds_difference(y_true, y_pred, sensitive_features=sf)),
        }
        try:
            out["eo"] = float(equal_opportunity_difference(y_true, y_pred, sensitive_features=sf))
        except Exception:
            out["eo"] = None  # type: ignore[assignment]
        return out
    except Exception:
        return None


def compute_fairness_metric(
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    sensitive: Iterable[Any],
    *,
    attribute: str = "group",
) -> FairnessMetric:
    """Compute all fairness metrics for ONE protected attribute (Fairlearn if available)."""
    yt, yp = _as_binary(y_true), _as_binary(y_pred)
    grp = _group_series(sensitive)
    sel = selection_rates(yp, grp)
    rates = group_tpr_fpr(yt, yp, grp)

    di = disparate_impact_ratio(yp, grp)
    # Direct computations (always correct, used as fallback + cross-check).
    dp_direct = _gap(sel.values())
    eo_direct = _gap(r["tpr"] for r in rates.values())
    eodds_direct = max(_gap(r["tpr"] for r in rates.values()), _gap(r["fpr"] for r in rates.values()))

    fl = _fairlearn_metrics(yt, yp, grp)
    if fl is not None:
        backend = "fairlearn"
        dp = fl["dp"]
        eodds = fl["eodds"]
        eo = fl["eo"] if fl.get("eo") is not None else eo_direct
    else:
        backend = "direct"
        dp, eo, eodds = dp_direct, eo_direct, eodds_direct

    return FairnessMetric(
        attribute=attribute,
        demographic_parity_difference=float(dp),
        disparate_impact_ratio=float(di),
        equal_opportunity_difference=float(eo),
        equalized_odds_difference=float(eodds),
        selection_rates=sel,
        group_rates=rates,
        backend=backend,
    )


# --------------------------------------------------------------------------- #
# Across all protected attributes                                             #
# --------------------------------------------------------------------------- #
def compute_all_fairness_metrics(
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    protected: pd.DataFrame,
    *,
    attributes: Optional[Iterable[str]] = None,
) -> dict[str, FairnessMetric]:
    """Compute fairness metrics for every protected attribute column present in ``protected``.

    ``protected`` is a DataFrame whose columns are protected attributes (grade, gender,
    region, branch, department, tenure, age, seniority). Continuous attributes (age,
    tenure) are auto-binned into quantile bands before grouping.
    """
    attrs = list(attributes) if attributes is not None else [
        c for c in PROTECTED_ATTRIBUTES if c in protected.columns
    ]
    out: dict[str, FairnessMetric] = {}
    for attr in attrs:
        if attr not in protected.columns:
            continue
        groups = _bin_if_continuous(protected[attr], attr)
        out[attr] = compute_fairness_metric(y_true, y_pred, groups, attribute=attr)
    return out


def _bin_if_continuous(col: pd.Series, name: str, n_bins: int = 4) -> pd.Series:
    """Quantile-bin a continuous protected attribute (age/tenure) into labelled bands.

    pandas-3.0-safe: uses ``pd.api.types`` rather than ``np.issubdtype`` on a Series.
    """
    if pd.api.types.is_numeric_dtype(col) and col.nunique(dropna=True) > n_bins:
        try:
            binned = pd.qcut(col, q=n_bins, duplicates="drop")
            return binned.astype(str).fillna("NA")
        except Exception:
            return col.astype(str)
    return col.astype(str)


# --------------------------------------------------------------------------- #
# ML-24 feed: metrics dict                                                     #
# --------------------------------------------------------------------------- #
def fairness_metrics_dict(
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    protected: pd.DataFrame,
    *,
    attributes: Optional[Iterable[str]] = None,
    gap_threshold: float = DEFAULT_GAP_THRESHOLD,
) -> dict[str, Any]:
    """Return a JSON-able metrics dict feeding ML-24 (model card fairness section).

    Shape::

        {
          "attributes": {attr: {...metric...}, ...},
          "any_breach": bool,
          "breaches": {attr: [breach_kind, ...]},
          "disparate_impact_floor": 0.8,
          "gap_threshold": 0.1,
        }
    """
    metrics = compute_all_fairness_metrics(y_true, y_pred, protected, attributes=attributes)
    breaches = {a: m.breaches(gap_threshold) for a, m in metrics.items()}
    breaches = {a: b for a, b in breaches.items() if b}
    return {
        "attributes": {a: m.to_dict() for a, m in metrics.items()},
        "any_breach": bool(breaches),
        "breaches": breaches,
        "disparate_impact_floor": DISPARATE_IMPACT_FLOOR,
        "gap_threshold": gap_threshold,
    }


# --------------------------------------------------------------------------- #
# Alerts: reason codes + narrative (ML-29.2 — every alert is contestable)      #
# --------------------------------------------------------------------------- #
_BREACH_DETAIL = {
    "disparate_impact": "Disparate-impact ratio below the 0.8 (4/5ths) rule",
    "demographic_parity": "Alert-rate gap across groups exceeds threshold",
    "equal_opportunity": "Recall (TPR) gap across groups exceeds threshold",
    "equalized_odds": "Combined TPR/FPR gap across groups exceeds threshold",
}


def fairness_alerts(
    metrics: dict[str, FairnessMetric],
    *,
    gap_threshold: float = DEFAULT_GAP_THRESHOLD,
    narrator: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    """Turn breached fairness metrics into alert payloads with reason codes + narrative.

    Each alert: {attribute, breaches, reason_codes(list[dict]), narrative, metric}. The
    narrative defaults to the deterministic template from ``ml.narrative`` (no LLM needed),
    so every fairness alert is explainable/contestable (blueprint Part 29.2).
    """
    if narrator is None:
        from ml.narrative import render_template as _render

        def narrator(ctx: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
            return {"narrative": _render(ctx), "provider": "template"}

    alerts: list[dict[str, Any]] = []
    for attr, m in metrics.items():
        kinds = m.breaches(gap_threshold)
        if not kinds:
            continue
        rcs = [
            ReasonCode(
                source="rule",
                code=f"fairness.{kind}.{attr}",
                detail=f"{_BREACH_DETAIL[kind]} (attribute={attr}, "
                f"DI={m.disparate_impact_ratio:.2f}, DP={m.demographic_parity_difference:.2f}, "
                f"EO={m.equal_opportunity_difference:.2f}, EOdds={m.equalized_odds_difference:.2f})",
            )
            for kind in kinds
        ]
        ctx = {
            "alert_id": f"fairness-{attr}",
            "entity_id": attr,
            "risk_score": min(100, int(round((1.0 - m.disparate_impact_ratio) * 100))),
            "severity": "high" if "disparate_impact" in kinds else "medium",
            "reason_codes": [rc.to_dict() for rc in rcs],
        }
        narr = narrator(ctx)
        alerts.append({
            "attribute": attr,
            "breaches": kinds,
            "reason_codes": [rc.to_dict() for rc in rcs],
            "narrative": narr.get("narrative"),
            "narrative_provider": narr.get("provider"),
            "metric": m.to_dict(),
        })
    return alerts


# --------------------------------------------------------------------------- #
# Continuous-monitoring hook (recompute on a new batch)                        #
# --------------------------------------------------------------------------- #
class FairnessMonitor:
    """Continuous-monitoring hook: recompute fairness metrics on each new batch.

    Holds the configuration (which attributes, thresholds) so a serving/eval loop can
    call ``monitor.update(y_true, y_pred, protected)`` on every incoming batch and get a
    fresh metrics dict + alerts. Keeps a bounded history of breach states so a regression
    (newly-introduced breach) can be detected over time.

    ALERT-ONLY: it never blocks; it raises fairness alerts that gate/notify.
    """

    def __init__(
        self,
        *,
        attributes: Optional[Iterable[str]] = None,
        gap_threshold: float = DEFAULT_GAP_THRESHOLD,
        history: int = 50,
        narrator: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
    ) -> None:
        self.attributes = list(attributes) if attributes is not None else None
        self.gap_threshold = gap_threshold
        self.narrator = narrator
        self._history: list[dict[str, Any]] = []
        self._max_history = history

    def update(
        self, y_true: Iterable[Any], y_pred: Iterable[Any], protected: pd.DataFrame
    ) -> dict[str, Any]:
        """Recompute on a new batch. Returns {metrics_dict, alerts, batch_index}."""
        metrics = compute_all_fairness_metrics(
            y_true, y_pred, protected, attributes=self.attributes
        )
        mdict = fairness_metrics_dict(
            y_true, y_pred, protected, attributes=self.attributes, gap_threshold=self.gap_threshold
        )
        alerts = fairness_alerts(metrics, gap_threshold=self.gap_threshold, narrator=self.narrator)
        record = {
            "batch_index": len(self._history),
            "metrics": mdict,
            "alerts": alerts,
            "any_breach": mdict["any_breach"],
        }
        self._history.append(record)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]
        return record

    # callable hook form, so it can be passed straight into a streaming loop.
    __call__ = update

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def newly_breached(self) -> list[str]:
        """Attributes that breached in the latest batch but not the prior one (regression)."""
        if len(self._history) < 2:
            return list(self._history[-1]["metrics"]["breaches"]) if self._history else []
        prev = set(self._history[-2]["metrics"]["breaches"])
        cur = set(self._history[-1]["metrics"]["breaches"])
        return sorted(cur - prev)
