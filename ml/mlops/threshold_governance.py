"""Alert-threshold governance (ML-22; blueprint Part 14 operational metrics).

The alert threshold is an *operational* lever, not just a statistical one: it has to fit
the analysts' daily throughput. This module tunes the score cut-off against:

* **analyst capacity / alert budgeting** — pick the threshold whose expected daily alert
  volume fits a configured daily budget (so the queue does not overflow),
* **precision@k** — precision among the top-k highest-scored alerts,
* **alert-to-true ratio** — alerts raised per confirmed-fraud case,
* **mean-time-to-disposition** — projected from queue depth and per-case handling time.

ALERT-ONLY: tuning a threshold changes WHICH alerts surface, never auto-blocks anyone.
HONEST EVAL: precision@k / alert-to-true are computed on labelled, time-split data.
No heavy model library is imported, so this loads in any process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import numpy as np

from ml.eval.metrics import precision_at_k


@dataclass
class ThresholdPoint:
    """The operating point at one candidate threshold."""

    threshold: float
    n_alerts: int
    alert_rate: float
    expected_daily_alerts: float
    precision: float
    recall: float
    precision_at_k: float
    alert_to_true_ratio: float
    mean_time_to_disposition_hours: float
    within_budget: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "threshold": round(self.threshold, 6),
            "n_alerts": self.n_alerts,
            "alert_rate": round(self.alert_rate, 6),
            "expected_daily_alerts": round(self.expected_daily_alerts, 2),
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "alert_to_true_ratio": round(self.alert_to_true_ratio, 4),
            "mean_time_to_disposition_hours": round(
                self.mean_time_to_disposition_hours, 3
            ),
            "within_budget": self.within_budget,
        }


def _confusion_at(
    y_true: np.ndarray, scores: np.ndarray, thr: float
) -> tuple[int, float, float, float]:
    """Return (#alerts, precision, recall, alert-to-true ratio) at a flag threshold."""
    flagged = scores >= thr
    n_alerts = int(flagged.sum())
    tp = float(np.sum(flagged & (y_true == 1)))
    fp = float(np.sum(flagged & (y_true == 0)))
    fn = float(np.sum(~flagged & (y_true == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    # alerts raised per true fraud surfaced (operational analyst burden); inf if no TP.
    atr = float(n_alerts / tp) if tp > 0 else float("inf")
    return n_alerts, precision, recall, atr


@dataclass
class ThresholdGovernanceResult:
    """The chosen operating point + the full sweep, against a daily capacity budget."""

    chosen: ThresholdPoint
    sweep: list[ThresholdPoint] = field(default_factory=list)
    daily_budget: int = 0
    objective: str = "precision_within_budget"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chosen": self.chosen.to_dict(),
            "daily_budget": self.daily_budget,
            "objective": self.objective,
            "sweep": [p.to_dict() for p in self.sweep],
        }


class ThresholdGovernor:
    """Tune the alert threshold to analyst throughput / a daily alert budget.

    ``daily_budget``      — max alerts analysts can disposition per day (alert budgeting).
    ``horizon_days``      — the period ``scores`` covers, used to project a daily volume.
    ``minutes_per_case``  — handling time per alert (for MTTD projection).
    ``analyst_hours_per_day`` — total analyst capacity per day (for MTTD projection).
    """

    def __init__(
        self,
        *,
        daily_budget: int = 50,
        horizon_days: float = 1.0,
        minutes_per_case: float = 30.0,
        analyst_hours_per_day: float = 16.0,
        k: int = 20,
    ) -> None:
        self.daily_budget = daily_budget
        self.horizon_days = max(horizon_days, 1e-9)
        self.minutes_per_case = minutes_per_case
        self.analyst_hours_per_day = max(analyst_hours_per_day, 1e-9)
        self.k = k

    def _point(
        self, y_true: np.ndarray, scores: np.ndarray, thr: float
    ) -> ThresholdPoint:
        n = len(scores)
        n_alerts, precision, recall, atr = _confusion_at(y_true, scores, thr)
        alert_rate = n_alerts / n if n else 0.0
        expected_daily = n_alerts / self.horizon_days
        # MTTD: how long the day's queue takes to clear given analyst capacity.
        capacity_per_day = (self.analyst_hours_per_day * 60.0) / max(
            self.minutes_per_case, 1e-9
        )
        backlog_factor = (
            expected_daily / capacity_per_day if capacity_per_day > 0 else 0.0
        )
        # base handling time + queue wait (grows with backlog beyond capacity).
        mttd_hours = (self.minutes_per_case / 60.0) * (1.0 + max(0.0, backlog_factor))
        # precision@k among flagged (k bounded by alerts raised).
        kk = min(self.k, n_alerts) if n_alerts else 0
        p_at_k = float(precision_at_k(y_true, scores, kk)) if kk else 0.0
        return ThresholdPoint(
            threshold=float(thr),
            n_alerts=n_alerts,
            alert_rate=alert_rate,
            expected_daily_alerts=expected_daily,
            precision=precision,
            recall=recall,
            precision_at_k=p_at_k,
            alert_to_true_ratio=atr,
            mean_time_to_disposition_hours=mttd_hours,
            within_budget=expected_daily <= self.daily_budget,
        )

    def sweep(
        self,
        y_true: Iterable[Any],
        scores: Iterable[float],
        *,
        grid: Optional[Iterable[float]] = None,
    ) -> list[ThresholdPoint]:
        yt = (np.asarray(list(y_true), dtype=float) >= 0.5).astype(int)
        sc = np.asarray(list(scores), dtype=float)
        if grid is None:
            qs = np.linspace(0.5, 0.999, 40)
            grid = np.unique(np.quantile(sc, qs)) if sc.size else np.array([0.5])
        return [self._point(yt, sc, float(t)) for t in grid]

    def tune(
        self,
        y_true: Iterable[Any],
        scores: Iterable[float],
        *,
        grid: Optional[Iterable[float]] = None,
    ) -> ThresholdGovernanceResult:
        """Choose the threshold that maximises precision while staying within the daily budget.

        Among operating points whose expected daily volume is within budget, pick the one
        with the highest precision (ties broken by higher recall). If NONE fit the budget
        (every threshold overflows), pick the most conservative (highest) threshold so the
        queue is as small as possible.
        """
        points = self.sweep(y_true, scores, grid=grid)
        if not points:
            raise ValueError("no scores to tune a threshold over")
        within = [p for p in points if p.within_budget]
        if within:
            chosen = max(
                within, key=lambda p: (p.precision, p.recall, -p.expected_daily_alerts)
            )
        else:
            chosen = max(points, key=lambda p: p.threshold)
        return ThresholdGovernanceResult(
            chosen=chosen,
            sweep=points,
            daily_budget=self.daily_budget,
            objective="precision_within_budget",
        )


__all__ = [
    "ThresholdPoint",
    "ThresholdGovernanceResult",
    "ThresholdGovernor",
]
