"""keep-if-beats-baselines gate (ML-5; blueprint §20.4, §22.2).

The L4 contract: a deep sequence model EARNS its place only if it beats the simple
baselines under HONEST (non-point-adjust) evaluation. This gate uses range/affiliation
-aware PR and VUS-PR from ``ml.eval`` — never point-adjust (assert it stays off).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from ml.eval import POINT_ADJUST_ENABLED, average_precision, vus_pr


@dataclass
class GateResult:
    keep: bool
    deep_vus_pr: float
    best_baseline_vus_pr: float
    deep_ap: float
    best_baseline_ap: float
    margin: float
    metric: str = "vus_pr"

    def to_dict(self) -> dict:
        return {
            "keep": self.keep,
            "metric": self.metric,
            "deep_vus_pr": round(self.deep_vus_pr, 4),
            "best_baseline_vus_pr": round(self.best_baseline_vus_pr, 4),
            "deep_ap": round(self.deep_ap, 4),
            "best_baseline_ap": round(self.best_baseline_ap, 4),
            "margin": round(self.margin, 4),
        }


def keep_if_beats_baselines(
    deep_scores: Sequence[float],
    baseline_scores,
    y: Sequence[int],
    *,
    metric: str = "vus_pr",
    min_margin: float = 0.0,
    max_buffer: int = 5,
) -> GateResult:
    """Return whether a deep model beats the best baseline under non-PA eval.

    ``baseline_scores`` may be a single score array or a dict ``name -> scores``.
    The deep model is kept only if its range/affiliation-aware metric exceeds the
    BEST baseline's by at least ``min_margin``. NEVER point-adjusts.
    """
    # Hard guarantee: this gate is honest.
    assert POINT_ADJUST_ENABLED is False, "point-adjust must stay disabled for L4 eval"
    if metric not in ("vus_pr", "average_precision"):
        raise ValueError(f"unsupported gate metric {metric!r}")

    y = np.asarray(y).astype(int).ravel()

    def _metric(scores) -> float:
        scores = np.asarray(scores, dtype=float).ravel()
        if metric == "vus_pr":
            return vus_pr(y, scores, max_buffer=max_buffer)
        return average_precision(y, scores)

    if isinstance(baseline_scores, dict):
        base_metrics = {k: _metric(v) for k, v in baseline_scores.items()}
        base_aps = {k: average_precision(y, np.asarray(v, dtype=float).ravel())
                    for k, v in baseline_scores.items()}
        best_base = max(base_metrics.values()) if base_metrics else 0.0
        best_base_ap = max(base_aps.values()) if base_aps else 0.0
    else:
        best_base = _metric(baseline_scores)
        best_base_ap = average_precision(y, np.asarray(baseline_scores, dtype=float).ravel())

    deep_m = _metric(deep_scores)
    deep_ap = average_precision(y, np.asarray(deep_scores, dtype=float).ravel())
    margin = deep_m - best_base
    return GateResult(
        keep=bool(margin > min_margin),
        deep_vus_pr=deep_m if metric == "vus_pr" else deep_ap,
        best_baseline_vus_pr=best_base if metric == "vus_pr" else best_base_ap,
        deep_ap=deep_ap,
        best_baseline_ap=best_base_ap,
        margin=float(margin),
        metric=metric,
    )


__all__ = ["keep_if_beats_baselines", "GateResult"]
