"""Shared imbalance utilities (ML-8; blueprint Part 5/20.3).

Reusable by L3/L4/L5: negative subsampling 1:3-1:10, class weights / scale_pos_weight /
focal loss, and a note that post-hoc calibration (ml.layers.l3.calibration) must follow.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml.config.seeds import GLOBAL_SEED


def negative_subsample(
    X: pd.DataFrame, y: pd.Series, ratio: float = 5.0, seed: int = GLOBAL_SEED
) -> tuple[pd.DataFrame, pd.Series]:
    """Keep all positives and ~``ratio``×positives negatives (ratio in 1:3..1:10).

    Returns the subsampled (X, y). Calibrate downstream so probabilities stay meaningful.
    """
    if not 1.0 <= ratio <= 20.0:
        raise ValueError("ratio should be in [1,20] (blueprint says 1:3..1:10)")
    yv = pd.to_numeric(y, errors="coerce").fillna(0).astype(int)
    pos_idx = yv.index[yv == 1]
    neg_idx = yv.index[yv == 0]
    n_keep = min(len(neg_idx), int(round(len(pos_idx) * ratio)))
    rng = np.random.default_rng(seed)
    keep_neg = rng.choice(neg_idx.to_numpy(), size=max(n_keep, 1), replace=False) if len(neg_idx) else np.array([])
    keep = np.concatenate([pos_idx.to_numpy(), keep_neg])
    rng.shuffle(keep)
    return X.loc[keep], yv.loc[keep]


def scale_pos_weight(y: pd.Series) -> float:
    """neg/pos ratio for XGBoost/LightGBM scale_pos_weight."""
    yv = pd.to_numeric(y, errors="coerce").fillna(0).astype(int)
    pos = int((yv == 1).sum())
    neg = int((yv == 0).sum())
    return float(neg / pos) if pos else 1.0


def class_weights(y: pd.Series) -> dict[int, float]:
    """Balanced class weights {0: w0, 1: w1} (sklearn 'balanced' convention)."""
    yv = pd.to_numeric(y, errors="coerce").fillna(0).astype(int)
    n = len(yv)
    out: dict[int, float] = {}
    for c in (0, 1):
        nc = int((yv == c).sum())
        out[c] = float(n / (2 * nc)) if nc else 1.0
    return out


def focal_loss_lgb(gamma: float = 2.0, alpha: float = 0.25):
    """A LightGBM custom focal-loss objective (grad, hess) for hard-example focus.

    Returns a callable ``obj(y_pred, dataset) -> (grad, hess)`` usable as LightGBM's fobj.
    """
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def obj(y_pred: np.ndarray, dataset) -> tuple[np.ndarray, np.ndarray]:
        y_true = dataset.get_label()
        p = _sigmoid(y_pred)
        # focal-loss gradient/hessian (binary), alpha-balanced
        pt = np.where(y_true == 1, p, 1 - p)
        alpha_t = np.where(y_true == 1, alpha, 1 - alpha)
        grad = alpha_t * (1 - pt) ** gamma * (gamma * pt * np.log(np.clip(pt, 1e-9, 1)) + pt - 1)
        grad = np.where(y_true == 1, grad, -grad)
        hess = np.abs(alpha_t * (1 - pt) ** gamma * pt * (1 - pt)) + 1e-6
        return grad, hess

    return obj


def focal_loss_value(y_true: np.ndarray, p: np.ndarray, gamma: float = 2.0, alpha: float = 0.25) -> float:
    """Scalar focal loss (for monitoring/tests)."""
    p = np.clip(p, 1e-9, 1 - 1e-9)
    pt = np.where(y_true == 1, p, 1 - p)
    alpha_t = np.where(y_true == 1, alpha, 1 - alpha)
    return float(-np.mean(alpha_t * (1 - pt) ** gamma * np.log(pt)))
