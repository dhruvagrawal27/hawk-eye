"""Drift detection + retrain trigger (ML-22; blueprint Part 18, 22.3).

Two drift families, with a crossing that fires an off-cycle retrain:

* **data drift** — per-feature distribution shift between a reference window and a current
  window, via **PSI** (population-stability index) and the **KS** two-sample statistic.
* **concept drift** — the model's *behaviour* decaying: rolling precision / recall computed
  over time-ordered EDD dispositions (so a drop in realised precision is caught even when
  the input features look stable).

Uses **Evidently** (``evidently``) when present (:func:`ml._optional.optional_import`) for
the data-drift report, with a self-contained **numpy PSI/KS fallback** that always works.
A :class:`RetrainTrigger` watches both signals and fires when a configured threshold is
crossed.

HONEST EVAL: concept drift is measured on time-ordered dispositions (never point-adjusted).
No heavy model library is imported, so this loads in any process.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_EVIDENTLY, optional_import

# PSI bands (industry convention): <0.1 stable, 0.1-0.25 moderate shift, >=0.25 significant.
PSI_MODERATE = 0.1
PSI_SIGNIFICANT = 0.25
# KS p-value below this rejects "same distribution" (drift).
KS_PVALUE_ALPHA = 0.05


# --------------------------------------------------------------------------- #
# numpy PSI / KS primitives (the always-on fallback)                          #
# --------------------------------------------------------------------------- #
def population_stability_index(
    reference: Iterable[float], current: Iterable[float], *, bins: int = 10
) -> float:
    """PSI between a reference and current sample. 0 = identical; grows with divergence.

    Bins are quantile edges of the reference (so each reference bin has ~equal mass); a
    small epsilon avoids div-by-zero / log(0) on empty bins.
    """
    ref = np.asarray(list(reference), dtype=float)
    cur = np.asarray(list(current), dtype=float)
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if ref.size == 0 or cur.size == 0:
        return 0.0
    # Quantile edges of the reference; dedupe so constant features don't explode.
    edges = np.unique(np.quantile(ref, np.linspace(0.0, 1.0, bins + 1)))
    if edges.size < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_hist, _ = np.histogram(ref, bins=edges)
    cur_hist, _ = np.histogram(cur, bins=edges)
    eps = 1e-6
    ref_pct = ref_hist / ref_hist.sum() + eps
    cur_pct = cur_hist / cur_hist.sum() + eps
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def ks_statistic(reference: Iterable[float], current: Iterable[float]) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov (statistic, p-value).

    Uses :func:`scipy.stats.ks_2samp` when SciPy is present (it ships with scikit-learn),
    else an exact empirical-CDF statistic with the asymptotic Kolmogorov p-value.
    """
    ref = np.asarray(list(reference), dtype=float)
    cur = np.asarray(list(current), dtype=float)
    ref = ref[np.isfinite(ref)]
    cur = cur[np.isfinite(cur)]
    if ref.size == 0 or cur.size == 0:
        return 0.0, 1.0
    try:  # SciPy ships with scikit-learn on the reference machine
        from scipy.stats import ks_2samp

        res = ks_2samp(ref, cur)
        return float(res.statistic), float(res.pvalue)
    except Exception:
        pass
    # numpy fallback: empirical-CDF sup-distance + asymptotic Kolmogorov p-value.
    allv = np.sort(np.concatenate([ref, cur]))
    cdf_ref = np.searchsorted(np.sort(ref), allv, side="right") / ref.size
    cdf_cur = np.searchsorted(np.sort(cur), allv, side="right") / cur.size
    stat = float(np.max(np.abs(cdf_ref - cdf_cur)))
    n_e = ref.size * cur.size / (ref.size + cur.size)
    lam = (np.sqrt(n_e) + 0.12 + 0.11 / np.sqrt(n_e)) * stat
    j = np.arange(1, 101)
    p = 2.0 * np.sum(((-1) ** (j - 1)) * np.exp(-2.0 * (lam**2) * (j**2)))
    return stat, float(min(max(p, 0.0), 1.0))


# --------------------------------------------------------------------------- #
# data drift across a feature matrix                                          #
# --------------------------------------------------------------------------- #
@dataclass
class FeatureDrift:
    feature: str
    psi: float
    ks_stat: float
    ks_pvalue: float

    @property
    def drifted(self) -> bool:
        return self.psi >= PSI_SIGNIFICANT or self.ks_pvalue < KS_PVALUE_ALPHA

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "psi": round(self.psi, 6),
            "ks_stat": round(self.ks_stat, 6),
            "ks_pvalue": round(self.ks_pvalue, 6),
            "drifted": self.drifted,
        }


@dataclass
class DataDriftReport:
    features: list[FeatureDrift] = field(default_factory=list)
    backend: str = "numpy"

    @property
    def n_drifted(self) -> int:
        return sum(1 for f in self.features if f.drifted)

    @property
    def share_drifted(self) -> float:
        return self.n_drifted / len(self.features) if self.features else 0.0

    @property
    def any_drift(self) -> bool:
        return self.n_drifted > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "n_features": len(self.features),
            "n_drifted": self.n_drifted,
            "share_drifted": round(self.share_drifted, 4),
            "any_drift": self.any_drift,
            "features": [f.to_dict() for f in self.features],
        }


def _numeric_columns(ref: pd.DataFrame, cur: pd.DataFrame) -> list[str]:
    cols = [c for c in ref.columns if c in cur.columns]
    # pandas-3.0-safe numeric check (never np.issubdtype on a Series).
    return [c for c in cols if pd.api.types.is_numeric_dtype(ref[c]) and pd.api.types.is_numeric_dtype(cur[c])]


def data_drift_report(
    reference: pd.DataFrame, current: pd.DataFrame, *, bins: int = 10, use_evidently: Optional[bool] = None
) -> DataDriftReport:
    """Per-feature PSI + KS drift between a reference and a current feature matrix.

    Always computes the numpy PSI/KS report (so the numbers are present and honest). When
    Evidently is available and not disabled, it additionally runs Evidently's drift report
    and records ``backend='evidently'`` (the per-feature PSI/KS we attach are still ours,
    keeping the contract stable across environments).
    """
    cols = _numeric_columns(reference, current)
    feats: list[FeatureDrift] = []
    for c in cols:
        psi = population_stability_index(reference[c], current[c], bins=bins)
        stat, pval = ks_statistic(reference[c], current[c])
        feats.append(FeatureDrift(feature=c, psi=psi, ks_stat=stat, ks_pvalue=pval))

    backend = "numpy"
    want_evidently = HAS_EVIDENTLY if use_evidently is None else use_evidently
    if want_evidently and HAS_EVIDENTLY:
        try:
            self_evidently = _run_evidently(reference[cols], current[cols])
            if self_evidently:
                backend = "evidently"
        except Exception:
            backend = "numpy"
    return DataDriftReport(features=feats, backend=backend)


def _run_evidently(reference: pd.DataFrame, current: pd.DataFrame) -> bool:  # pragma: no cover - optional path
    """Run an Evidently data-drift report; return True on success (API varies by version)."""
    evidently = optional_import("evidently")
    if evidently is None:
        return False
    # Evidently's public API has shifted across 0.4->0.7; try the common entrypoints and
    # treat any successful run as a confirmation. We don't depend on its exact output shape.
    try:
        from evidently import Report
        from evidently.presets import DataDriftPreset

        rep = Report(metrics=[DataDriftPreset()])
        rep.run(reference_data=reference, current_data=current)
        return True
    except Exception:
        try:
            from evidently.report import Report  # type: ignore
            from evidently.metric_preset import DataDriftPreset  # type: ignore

            rep = Report(metrics=[DataDriftPreset()])
            rep.run(reference_data=reference, current_data=current)
            return True
        except Exception:
            return False


# --------------------------------------------------------------------------- #
# concept drift: rolling precision / recall over dispositions                  #
# --------------------------------------------------------------------------- #
@dataclass
class ConceptDriftReport:
    windows: list[dict[str, float]] = field(default_factory=list)
    precision_drop: float = 0.0
    recall_drop: float = 0.0
    baseline_precision: float = 0.0
    latest_precision: float = 0.0
    baseline_recall: float = 0.0
    latest_recall: float = 0.0

    @property
    def degraded(self) -> bool:
        return self.precision_drop > 0 or self.recall_drop > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "windows": self.windows,
            "baseline_precision": round(self.baseline_precision, 4),
            "latest_precision": round(self.latest_precision, 4),
            "precision_drop": round(self.precision_drop, 4),
            "baseline_recall": round(self.baseline_recall, 4),
            "latest_recall": round(self.latest_recall, 4),
            "recall_drop": round(self.recall_drop, 4),
            "degraded": self.degraded,
        }


def rolling_precision_recall(
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    *,
    window: int = 50,
    step: Optional[int] = None,
) -> ConceptDriftReport:
    """Rolling precision/recall over TIME-ORDERED dispositions (concept-drift signal).

    ``y_true``/``y_pred`` must already be ordered by disposition time (earliest first).
    Each window yields (precision, recall); the report compares the FIRST window (baseline)
    to the LAST (latest) and reports the drop, so decay is detected without point-adjusting.
    """
    yt = np.asarray(list(y_true), dtype=float)
    yp = np.asarray(list(y_pred), dtype=float)
    if yp.size and not np.array_equal(yp, yp.astype(int)):
        yp = (yp >= 0.5).astype(float)
    n = len(yt)
    if n == 0:
        return ConceptDriftReport()
    window = max(1, min(window, n))
    step = step or window
    rows: list[dict[str, float]] = []
    for start in range(0, n - window + 1, step):
        wt = yt[start : start + window]
        wp = yp[start : start + window]
        tp = float(np.sum((wp == 1) & (wt == 1)))
        fp = float(np.sum((wp == 1) & (wt == 0)))
        fn = float(np.sum((wp == 0) & (wt == 1)))
        prec = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
        rec = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
        rows.append({"start": float(start), "precision": prec, "recall": rec})
    if not rows:
        rows.append({"start": 0.0, "precision": float("nan"), "recall": float("nan")})

    def _val(idx: int, key: str, default: float) -> float:
        v = rows[idx][key]
        return default if (v is None or np.isnan(v)) else float(v)

    base_p, last_p = _val(0, "precision", 0.0), _val(-1, "precision", 0.0)
    base_r, last_r = _val(0, "recall", 0.0), _val(-1, "recall", 0.0)
    return ConceptDriftReport(
        windows=rows,
        baseline_precision=base_p,
        latest_precision=last_p,
        precision_drop=max(0.0, base_p - last_p),
        baseline_recall=base_r,
        latest_recall=last_r,
        recall_drop=max(0.0, base_r - last_r),
    )


# --------------------------------------------------------------------------- #
# retrain trigger                                                              #
# --------------------------------------------------------------------------- #
@dataclass
class RetrainSignal:
    triggered: bool
    reasons: list[str] = field(default_factory=list)
    data_drift: Optional[dict[str, Any]] = None
    concept_drift: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "triggered": self.triggered,
            "reasons": self.reasons,
            "data_drift": self.data_drift,
            "concept_drift": self.concept_drift,
        }


class RetrainTrigger:
    """Fires an off-cycle retrain when a drift threshold is crossed (blueprint Part 22.3).

    A retrain is triggered if EITHER:
      * the share of features showing significant data drift exceeds ``drift_share_threshold``,
        OR any single feature's PSI exceeds ``psi_threshold``; OR
      * concept-drift precision/recall drop exceeds ``metric_drop_threshold``.
    """

    def __init__(
        self,
        *,
        psi_threshold: float = PSI_SIGNIFICANT,
        drift_share_threshold: float = 0.3,
        metric_drop_threshold: float = 0.1,
    ) -> None:
        self.psi_threshold = psi_threshold
        self.drift_share_threshold = drift_share_threshold
        self.metric_drop_threshold = metric_drop_threshold

    def evaluate(
        self,
        *,
        data_drift: Optional[DataDriftReport] = None,
        concept_drift: Optional[ConceptDriftReport] = None,
    ) -> RetrainSignal:
        reasons: list[str] = []
        if data_drift is not None:
            if data_drift.share_drifted >= self.drift_share_threshold:
                reasons.append(
                    f"data drift: {data_drift.share_drifted:.0%} of features drifted "
                    f">= {self.drift_share_threshold:.0%} threshold"
                )
            max_psi = max((f.psi for f in data_drift.features), default=0.0)
            if max_psi >= self.psi_threshold and not reasons:
                # a single feature with a large PSI is itself enough
                worst = max(data_drift.features, key=lambda f: f.psi)
                reasons.append(
                    f"data drift: feature {worst.feature!r} PSI {max_psi:.3f} "
                    f">= {self.psi_threshold:.3f} threshold"
                )
        if concept_drift is not None:
            if concept_drift.precision_drop >= self.metric_drop_threshold:
                reasons.append(
                    f"concept drift: precision dropped {concept_drift.precision_drop:.3f} "
                    f">= {self.metric_drop_threshold:.3f} threshold"
                )
            if concept_drift.recall_drop >= self.metric_drop_threshold:
                reasons.append(
                    f"concept drift: recall dropped {concept_drift.recall_drop:.3f} "
                    f">= {self.metric_drop_threshold:.3f} threshold"
                )
        return RetrainSignal(
            triggered=bool(reasons),
            reasons=reasons,
            data_drift=data_drift.to_dict() if data_drift else None,
            concept_drift=concept_drift.to_dict() if concept_drift else None,
        )


__all__ = [
    "PSI_MODERATE",
    "PSI_SIGNIFICANT",
    "KS_PVALUE_ALPHA",
    "population_stability_index",
    "ks_statistic",
    "FeatureDrift",
    "DataDriftReport",
    "data_drift_report",
    "ConceptDriftReport",
    "rolling_precision_recall",
    "RetrainSignal",
    "RetrainTrigger",
]
