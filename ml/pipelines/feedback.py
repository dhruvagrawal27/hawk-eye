"""EDD feedback loop (ML-16; blueprint Part 22.3).

Consume the labeled disposition store (:class:`ml.adapters.LabelStore`), prioritise the
NEXT cases to label by **uncertainty + high value** (active learning), trigger a scheduled
retrain that **consumes the new labels**, and provide an A/B comparison between the
champion and the retrained challenger that is COMPARABLE (same held-out eval).

ALERT-ONLY + HONEST EVAL hold throughout: retrains are time-split and never point-adjust.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ml.adapters import Disposition, LabelStore
from ml.eval import average_precision, temporal_split
from ml.layers.l3 import CalibratedScorer, LightGBMScorer
from ml.strategies import negative_subsample


# --------------------------------------------------------------------------- #
# active learning: which cases to send to investigators next                  #
# --------------------------------------------------------------------------- #
def uncertainty(p: np.ndarray) -> np.ndarray:
    """Uncertainty = 1 - 2*|p - 0.5| (max at p=0.5). Higher => more informative to label."""
    p = np.clip(np.asarray(p, dtype=float).ravel(), 0.0, 1.0)
    return 1.0 - 2.0 * np.abs(p - 0.5)


def active_learning_priority(
    p: np.ndarray,
    value: Optional[np.ndarray] = None,
    *,
    value_weight: float = 0.5,
) -> np.ndarray:
    """Rank score: blend model uncertainty with (log) exposure value.

    Uncertain AND high-value cases sort to the top — the blueprint's active-learning
    selection (Part 22.3): label the cases that are both informative and expensive.
    """
    u = uncertainty(p)
    if value is None:
        return u
    v = np.asarray(value, dtype=float).ravel()
    v = np.log1p(np.clip(v, 0, None))
    span = float(np.ptp(v)) or 1.0
    v = (v - v.min()) / span
    return (1.0 - value_weight) * u + value_weight * v


@dataclass
class ActiveLearningBatch:
    indices: np.ndarray
    priorities: np.ndarray
    entity_ids: list[str] = field(default_factory=list)


def select_for_labeling(
    X: pd.DataFrame,
    p: np.ndarray,
    *,
    value: Optional[np.ndarray] = None,
    batch_size: int = 20,
    value_weight: float = 0.5,
) -> ActiveLearningBatch:
    """Pick the top-``batch_size`` cases to send to EDD by active-learning priority."""
    prio = active_learning_priority(p, value, value_weight=value_weight)
    k = max(1, min(batch_size, len(prio)))
    order = np.argsort(-prio)[:k]
    ids = [str(X.index[i]) for i in order]
    return ActiveLearningBatch(indices=order, priorities=prio[order], entity_ids=ids)


# --------------------------------------------------------------------------- #
# scheduled retrain that consumes new labels                                  #
# --------------------------------------------------------------------------- #
@dataclass
class RetrainResult:
    challenger: CalibratedScorer
    champion_auprc: float
    challenger_auprc: float
    n_base_labels: int
    n_new_labels: int
    promote: bool

    @property
    def ab_comparable(self) -> bool:
        return np.isfinite(self.champion_auprc) and np.isfinite(self.challenger_auprc)


def merge_disposition_labels(
    base_y: pd.Series,
    store: LabelStore,
) -> tuple[pd.Series, int]:
    """Overlay EDD disposition labels (by event_id) onto the base label Series.

    Returns (merged_y, n_new) where ``n_new`` is how many base labels the dispositions
    changed/added — i.e. evidence the retrain actually CONSUMED new labels.
    """
    merged = base_y.copy()
    edd = store.labels()
    n_new = 0
    if not edd.empty:
        edd_map = edd.set_index("event_id")["is_fraud"].astype(int)
        for eid, val in edd_map.items():
            if eid in merged.index and int(merged.loc[eid]) != int(val):
                n_new += 1
            elif eid not in merged.index:
                n_new += 1
            merged.loc[eid] = int(val)
    return merged.astype(int), n_new


def scheduled_retrain(
    X: pd.DataFrame,
    base_y: pd.Series,
    store: LabelStore,
    ts: Optional[pd.Series] = None,
    *,
    champion: Optional[CalibratedScorer] = None,
    n_estimators: int = 300,
    test_frac: float = 0.25,
    seed: int = 1405,
) -> RetrainResult:
    """Retrain on base labels + new EDD dispositions; A/B vs champion on a held-out future.

    The challenger consumes the merged labels; both models are scored on the SAME time
    -based test block so the comparison is honest and comparable.
    """
    X = X.reset_index(drop=False)
    id_col = X.columns[0]
    X = X.set_index(id_col)
    base_y = pd.Series(np.asarray(base_y).astype(int).ravel(), index=X.index)

    merged_y, n_new = merge_disposition_labels(base_y, store)

    if ts is None:
        ts = pd.Series(np.arange(len(X)), index=X.index)
    df = X.copy()
    df["__y__"] = merged_y.to_numpy()
    df["__yb__"] = base_y.to_numpy()
    df["__ts__"] = np.asarray(ts)
    tr, te = temporal_split(df, "__ts__", test_frac=test_frac)
    feat_cols = [c for c in X.columns]
    Xtr, Xte = tr[feat_cols].reset_index(drop=True), te[feat_cols].reset_index(
        drop=True
    )
    ytr_new = tr["__y__"].astype(int).reset_index(drop=True)
    yte = te["__y__"].astype(int).reset_index(drop=True)

    def _fit(yv: pd.Series) -> CalibratedScorer:
        Xs, ys = (
            negative_subsample(Xtr, yv, ratio=5.0, seed=seed)
            if int(yv.sum()) >= 2
            else (Xtr, yv)
        )
        Xs = Xs.sort_index().reset_index(drop=True)
        ys = ys.sort_index().reset_index(drop=True)
        sc = CalibratedScorer(
            LightGBMScorer(n_estimators=n_estimators, use_scale_pos_weight=True),
            method="isotonic",
        )
        sc.fit(Xs, ys)
        return sc

    challenger = _fit(ytr_new)

    # champion: either the provided one, or a model trained on BASE labels only.
    if champion is None:
        champion = _fit(tr["__yb__"].astype(int).reset_index(drop=True))

    if len(Xte) and int(yte.sum()) > 0:
        champ_ap = average_precision(yte, champion.predict_proba(Xte))
        chal_ap = average_precision(yte, challenger.predict_proba(Xte))
    else:
        champ_ap = chal_ap = float("nan")

    promote = bool(
        np.isfinite(chal_ap) and np.isfinite(champ_ap) and chal_ap >= champ_ap
    )
    return RetrainResult(
        challenger=challenger,
        champion_auprc=champ_ap,
        challenger_auprc=chal_ap,
        n_base_labels=int(base_y.sum()),
        n_new_labels=n_new,
        promote=promote,
    )


__all__ = [
    "uncertainty",
    "active_learning_priority",
    "select_for_labeling",
    "ActiveLearningBatch",
    "merge_disposition_labels",
    "scheduled_retrain",
    "RetrainResult",
    "Disposition",
]
