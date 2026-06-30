"""L3 supervised training (ML-15; blueprint Part 22.2).

Time-aware CV + early stopping + scale_pos_weight + 1:3-1:10 negative subsample
(``ml.strategies``) + isotonic calibration -> AUPRC / Rec@K -> register.

Returns a fitted, CALIBRATED scorer plus an honest (time-split) metric report. Stays
LightGBM-only (no torch) so it is safe to run in a process that already loaded LightGBM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.eval import average_precision, recall_at_k, temporal_split, time_aware_cv
from ml.layers.l3 import CalibratedScorer, LightGBMScorer
from ml.strategies import negative_subsample, scale_pos_weight


@dataclass
class L3TrainResult:
    scorer: CalibratedScorer
    metrics: dict[str, float]
    cv_ap: list[float] = field(default_factory=list)
    spw: float = 1.0
    n_train: int = 0
    n_test: int = 0

    @property
    def calibrated(self) -> bool:
        return True


def train_l3(
    X: pd.DataFrame,
    y: pd.Series,
    ts: Optional[pd.Series] = None,
    *,
    subsample_ratio: float = 5.0,
    n_estimators: int = 400,
    n_cv_splits: int = 3,
    test_frac: float = 0.25,
    rec_at_k: int = 50,
    seed: int = 1405,
) -> L3TrainResult:
    """Honest L3 training: time split -> subsample+spw fit -> isotonic calibrate -> AUPRC/Rec@K."""
    X = X.reset_index(drop=True)
    y = pd.Series(np.asarray(y).astype(int).ravel())
    if ts is None:
        ts = pd.Series(np.arange(len(X)))
    ts = pd.Series(np.asarray(ts)).reset_index(drop=True)

    # ----- time-based train/test split (NEVER random) -----
    df = X.copy()
    df["__y__"] = y.to_numpy()
    df["__ts__"] = ts.to_numpy()
    tr, te = temporal_split(df, "__ts__", test_frac=test_frac)
    Xtr = tr.drop(columns=["__y__", "__ts__"]).reset_index(drop=True)
    ytr = tr["__y__"].astype(int).reset_index(drop=True)
    Xte = te.drop(columns=["__y__", "__ts__"]).reset_index(drop=True)
    yte = te["__y__"].astype(int).reset_index(drop=True)

    # ----- time-aware CV on the training block (expanding window) -----
    cv_ap: list[float] = []
    if int(ytr.sum()) >= 2:
        for tr_idx, va_idx in time_aware_cv(tr, "__ts__", n_splits=n_cv_splits):
            Xc, yc = Xtr.iloc[tr_idx], ytr.iloc[tr_idx]
            Xv, yv = Xtr.iloc[va_idx], ytr.iloc[va_idx]
            if int(yc.sum()) == 0 or int(yv.sum()) == 0:
                continue
            base = LightGBMScorer(n_estimators=n_estimators, use_scale_pos_weight=True,
                                  random_state=seed)
            base.fit(Xc, yc)
            cv_ap.append(average_precision(yv, base.predict_proba(Xv)))

    # ----- imbalance: 1:3-1:10 negative subsample + scale_pos_weight -----
    spw = scale_pos_weight(ytr)
    Xss, yss = negative_subsample(Xtr, ytr, ratio=subsample_ratio, seed=seed)
    # keep time order after subsample so the early-stopping tail stays "future"
    order = np.argsort(Xss.index.to_numpy())
    Xss = Xss.iloc[order].reset_index(drop=True)
    yss = yss.iloc[order].reset_index(drop=True)

    base = LightGBMScorer(n_estimators=n_estimators, use_scale_pos_weight=True, random_state=seed)
    # ----- isotonic calibration on a held-out tail (refits base internally) -----
    scorer = CalibratedScorer(base, method="isotonic", valid_frac=0.25)
    scorer.fit(Xss, yss)

    # ----- honest eval on the FUTURE test block -----
    if len(Xte) and int(yte.sum()) > 0:
        p = scorer.predict_proba(Xte)
        metrics = {
            "auprc": average_precision(yte, p),
            f"recall_at_{rec_at_k}": recall_at_k(yte, p, rec_at_k),
        }
    else:
        metrics = {"auprc": float("nan"), f"recall_at_{rec_at_k}": float("nan")}
    metrics["cv_auprc_mean"] = float(np.mean(cv_ap)) if cv_ap else float("nan")

    return L3TrainResult(
        scorer=scorer, metrics=metrics, cv_ap=cv_ap, spw=spw,
        n_train=len(Xtr), n_test=len(Xte),
    )


__all__ = ["train_l3", "L3TrainResult"]
