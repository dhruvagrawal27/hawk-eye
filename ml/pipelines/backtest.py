"""Backtest harness (ML-19; blueprint Part 14).

Replay historical events through candidate models and estimate two business numbers an
investigations lead actually cares about:

* **detection lift** — how much more true fraud the candidate catches in a fixed alert
  budget (top-K) versus a baseline (random, or the current champion). Expressed as a
  ratio and as extra true positives caught.
* **false-positive cost** — the analyst-time cost of the false alarms the candidate
  raises at its operating threshold (FP count × per-investigation cost).

Honest by construction: backtests replay in TIME ORDER and never point-adjust.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.eval import (
    POINT_ADJUST_ENABLED,
    average_precision,
    precision_at_k,
    recall_at_k,
)


@dataclass
class BacktestResult:
    model_version: str
    auprc: float
    precision_at_k: float
    recall_at_k: float
    k: int
    detection_lift: float           # candidate TPs@K / baseline TPs@K
    extra_true_positives: int       # candidate TPs@K - baseline TPs@K
    false_positives: int            # FPs in the alerting set (>= threshold)
    fp_cost: float                  # FPs × per-investigation cost
    n_events: int = 0
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "auprc": round(self.auprc, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "recall_at_k": round(self.recall_at_k, 4),
            "k": self.k,
            "detection_lift": round(self.detection_lift, 4),
            "extra_true_positives": self.extra_true_positives,
            "false_positives": self.false_positives,
            "fp_cost": round(self.fp_cost, 2),
            "n_events": self.n_events,
        }


def _tp_at_k(y: np.ndarray, scores: np.ndarray, k: int) -> int:
    top = np.argsort(-scores)[:k]
    return int(y[top].sum())


def backtest(
    y: pd.Series,
    scores: np.ndarray,
    *,
    model_version: str = "candidate",
    k: int = 50,
    threshold: float = 0.5,
    fp_cost_per_case: float = 1500.0,
    baseline_scores: Optional[np.ndarray] = None,
) -> BacktestResult:
    """Estimate detection-lift + FP-cost for one candidate's replayed scores.

    ``baseline_scores`` defaults to a uniform-random baseline (the honest 'do nothing
    smart' comparator) so detection lift is always defined.
    """
    assert POINT_ADJUST_ENABLED is False, "backtest must never point-adjust"
    yv = np.asarray(y).astype(int).ravel()
    s = np.asarray(scores, dtype=float).ravel()
    k = max(1, min(int(k), yv.size))

    if baseline_scores is None:
        rng = np.random.default_rng(1405)
        base = rng.random(yv.size)
    else:
        base = np.asarray(baseline_scores, dtype=float).ravel()

    tp_cand = _tp_at_k(yv, s, k)
    tp_base = _tp_at_k(yv, base, k)
    lift = float(tp_cand / tp_base) if tp_base > 0 else (float(tp_cand) if tp_cand > 0 else 1.0)

    # FP cost at the operating threshold.
    alerted = s >= threshold
    false_pos = int(((alerted) & (yv == 0)).sum())
    fp_cost = float(false_pos * fp_cost_per_case)

    ap = average_precision(yv, s)
    p_at_k = precision_at_k(yv, s, k)
    r_at_k = recall_at_k(yv, s, k)

    return BacktestResult(
        model_version=model_version,
        auprc=ap,
        precision_at_k=p_at_k,
        recall_at_k=r_at_k,
        k=k,
        detection_lift=lift,
        extra_true_positives=int(tp_cand - tp_base),
        false_positives=false_pos,
        fp_cost=fp_cost,
        n_events=int(yv.size),
        metrics={"auprc": ap, "precision_at_k": p_at_k, "recall_at_k": r_at_k},
    )


def compare_candidates(
    y: pd.Series,
    candidates: dict[str, np.ndarray],
    *,
    k: int = 50,
    threshold: float = 0.5,
    fp_cost_per_case: float = 1500.0,
) -> list[BacktestResult]:
    """Backtest several candidates against a shared random baseline; sort by detection lift."""
    results = [
        backtest(y, sc, model_version=name, k=k, threshold=threshold,
                 fp_cost_per_case=fp_cost_per_case)
        for name, sc in candidates.items()
    ]
    return sorted(results, key=lambda r: r.detection_lift, reverse=True)


__all__ = ["backtest", "BacktestResult", "compare_candidates"]
