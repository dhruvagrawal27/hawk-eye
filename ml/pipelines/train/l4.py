"""L4 sequence training (ML-15; blueprint Part 22.2, 20.4).

Windowed baselines FIRST, then OPTIONAL deep — and keep the deep model ONLY if it beats
the baselines under HONEST (non-point-adjust) evaluation (``ml.layers.l4.gate``). Eval is
split by time; point-adjust is never used.

By default this trains only the simple baselines (torch-free). A deep model may be passed
in; its scores are gated against the best baseline before it is "kept".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ml.eval import POINT_ADJUST_ENABLED, average_precision, vus_pr
from ml.layers.l4 import (
    GateResult,
    WindowSet,
    build_windows,
    keep_if_beats_baselines,
    run_baselines_first,
)


@dataclass
class L4TrainResult:
    baseline_scores: dict[str, np.ndarray]
    baseline_ap: dict[str, float]
    best_baseline: str
    windows: WindowSet
    gate: Optional[GateResult] = None
    kept_deep: bool = False
    deep_name: Optional[str] = None
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def calibrated(self) -> bool:
        # L4 keeps thresholds on validation; "calibrated" == baselines fitted + evaluated.
        return bool(self.baseline_ap)


def train_l4(
    events: pd.DataFrame,
    labels: Optional[pd.Series] = None,
    *,
    window: int = 20,
    deep_scores_fn: Optional[Callable[[WindowSet], np.ndarray]] = None,
    deep_name: Optional[str] = None,
    gate_metric: str = "vus_pr",
    min_margin: float = 0.0,
) -> L4TrainResult:
    """Build windows -> run baselines first -> evaluate (non-PA) -> gate optional deep model.

    ``deep_scores_fn`` maps the WindowSet to per-window anomaly scores (e.g. a fitted
    USAD/TranAD ``score_samples``). It is only KEPT if it beats the best baseline.
    """
    assert POINT_ADJUST_ENABLED is False, "L4 eval must never point-adjust"

    # build_windows aligns labels to events.index (positional). If the label Series is
    # keyed by event_id (the FeatureSource convention), remap it onto events.index first.
    labels = _align_labels_to_events(events, labels)
    ws = build_windows(events, labels=labels, window=window)
    base_scores = run_baselines_first(ws, window=window)
    y = ws.y

    base_ap = {name: average_precision(y, s) for name, s in base_scores.items()}
    best_baseline = max(base_ap, key=lambda k: base_ap[k]) if base_ap else ""

    metrics: dict[str, float] = {f"baseline_ap_{k}": v for k, v in base_ap.items()}
    metrics["best_baseline_ap"] = base_ap.get(best_baseline, float("nan"))
    if base_scores:
        metrics["best_baseline_vus_pr"] = max(
            vus_pr(y, s) for s in base_scores.values()
        )

    gate: Optional[GateResult] = None
    kept = False
    if deep_scores_fn is not None:
        deep = np.asarray(deep_scores_fn(ws), dtype=float).ravel()
        gate = keep_if_beats_baselines(
            deep, base_scores, y, metric=gate_metric, min_margin=min_margin
        )
        kept = gate.keep
        metrics["deep_vus_pr"] = gate.deep_vus_pr
        metrics["deep_ap"] = gate.deep_ap
        metrics["gate_margin"] = gate.margin

    return L4TrainResult(
        baseline_scores=base_scores,
        baseline_ap=base_ap,
        best_baseline=best_baseline,
        windows=ws,
        gate=gate,
        kept_deep=kept,
        deep_name=deep_name if kept else None,
        metrics=metrics,
    )


def _align_labels_to_events(
    events: pd.DataFrame, labels: Optional[pd.Series]
) -> Optional[pd.Series]:
    """Return a 0/1 label Series aligned to ``events.index`` (handles event_id-keyed labels)."""
    if labels is None:
        return None
    labels = pd.Series(
        np.asarray(labels).astype(int).ravel(),
        index=getattr(labels, "index", events.index),
    )
    # already aligned to events.index -> keep
    if labels.index.equals(events.index):
        return labels
    # event_id-keyed -> map through the events' event_id column
    if "event_id" in events.columns:
        m = labels.reindex(events["event_id"].to_numpy()).to_numpy()
        return pd.Series(np.nan_to_num(m).astype(int), index=events.index)
    # fall back to positional if lengths match
    if len(labels) == len(events):
        return pd.Series(labels.to_numpy(), index=events.index)
    return labels.reindex(events.index).fillna(0).astype(int)


__all__ = ["train_l4", "L4TrainResult"]
