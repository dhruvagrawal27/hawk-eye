"""Class-imbalance utilities for L3 supervised GBDT (ML-4; blueprint Part 20.3, 5.5).

Fraud is extreme-imbalance (~0.5-1% positive). The blueprint prescribes a combination:
1:3-1:10 negative subsample + class weights / scale_pos_weight + (optionally) focal loss,
then post-hoc calibration (see ``calibration.py``). These helpers are reusable across the
three tree scorers so they all share one definition of "how we handle imbalance".

pandas-3.0-safe (no ``np.issubdtype`` on Series dtypes). No heavy deps at module import.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def _as_label_array(y) -> np.ndarray:
    """Coerce a label container (Series/array/list) to a 0/1 int numpy array."""
    if isinstance(y, pd.Series):
        arr = pd.to_numeric(y, errors="coerce").fillna(0).to_numpy()
    else:
        arr = np.asarray(y)
        if arr.dtype == bool:
            arr = arr.astype(int)
    return (np.asarray(arr).ravel() > 0).astype(int)


def class_counts(y) -> tuple[int, int]:
    """Return ``(n_negative, n_positive)``."""
    arr = _as_label_array(y)
    pos = int(arr.sum())
    neg = int(arr.size - pos)
    return neg, pos


def scale_pos_weight(y) -> float:
    """``neg/pos`` weight for XGBoost/LightGBM (blueprint Part 20.3).

    Returns 1.0 when there are no positives (degenerate; avoids div-by-zero).
    """
    neg, pos = class_counts(y)
    if pos == 0:
        return 1.0
    return float(neg) / float(pos)


def class_weight_dict(y) -> dict[int, float]:
    """Balanced per-class weights (``n_samples / (n_classes * n_class)``) for sklearn estimators."""
    neg, pos = class_counts(y)
    n = neg + pos
    if pos == 0 or neg == 0:
        return {0: 1.0, 1: 1.0}
    return {0: n / (2.0 * neg), 1: n / (2.0 * pos)}


def sample_weight(y) -> np.ndarray:
    """Per-row sample weight from the balanced class weights (for ``fit(sample_weight=...)``)."""
    arr = _as_label_array(y)
    cw = class_weight_dict(arr)
    return np.where(arr == 1, cw[1], cw[0]).astype(float)


def negative_subsample(
    X,
    y,
    ratio: float = 5.0,
    *,
    seed: int = 1405,
) -> tuple[pd.DataFrame, pd.Series, np.ndarray]:
    """Subsample the majority (negative) class to ``ratio`` negatives per positive.

    ``ratio`` is the blueprint's 1:3-1:10 band (default 1:5). Keeps ALL positives and a
    random ``ratio * n_pos`` negatives. Time order of the kept rows is preserved so a
    downstream temporal split is still valid. Returns ``(X_sub, y_sub, kept_index_positions)``
    where the positions index into the original row order.

    If there are too few negatives to reach the ratio, all negatives are kept.
    """
    if not 1.0 <= ratio <= 50.0:
        raise ValueError(f"ratio {ratio} out of the sane 1:1..1:50 band")
    yarr = _as_label_array(y)
    pos_pos = np.flatnonzero(yarr == 1)
    neg_pos = np.flatnonzero(yarr == 0)
    n_keep_neg = min(neg_pos.size, int(round(ratio * pos_pos.size)))
    rng = np.random.default_rng(seed)
    kept_neg = rng.choice(neg_pos, size=n_keep_neg, replace=False) if n_keep_neg > 0 else np.array([], dtype=int)
    kept = np.sort(np.concatenate([pos_pos, kept_neg])).astype(int)

    X_sub = X.iloc[kept] if isinstance(X, (pd.DataFrame, pd.Series)) else np.asarray(X)[kept]
    if isinstance(y, pd.Series):
        y_sub = y.iloc[kept]
    else:
        y_sub = pd.Series(yarr[kept])
    return X_sub, y_sub, kept


def focal_loss_objective(gamma: float = 2.0, alpha: float = 0.25):
    """A binary-focal-loss objective callable for gradient-boosted trees.

    Returns ``obj(y_true, raw_pred) -> (grad, hess)`` matching the LightGBM/XGBoost custom
    objective signature on raw (logit) margins. Focal loss down-weights easy negatives so
    the model focuses on the rare, hard positives (Lin et al. 2017; blueprint Part 20.3/5.5).

    The closed-form grad/hess below are the standard focal-loss derivatives w.r.t. the raw
    logit ``z`` with ``p = sigmoid(z)``. Numerically guarded so it never returns NaN/inf.
    """

    def _sigmoid(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))

    def obj(y_true, raw_pred):
        y = _as_label_array(y_true).astype(float)
        z = np.asarray(raw_pred, dtype=float).ravel()
        p = _sigmoid(z)
        eps = 1e-9
        p = np.clip(p, eps, 1.0 - eps)
        # alpha weighting per class.
        a = np.where(y == 1, alpha, 1.0 - alpha)
        # pt = prob of the true class.
        pt = np.where(y == 1, p, 1.0 - p)
        # grad/hess of focal loss w.r.t. raw logit z.
        # d/dz of -a*(1-pt)^gamma*log(pt). Standard derivation (sign per class via (p - y)).
        term = (1.0 - pt) ** gamma
        # gradient
        g = a * term * (
            gamma * pt * np.log(pt) + pt - 1.0
        ) * np.where(y == 1, 1.0, -1.0) * -1.0
        grad = a * (p - y) * ((1.0 - pt) ** (gamma - 1.0)) * (
            (1.0 - pt) - gamma * pt * np.log(pt)
        )
        # hessian: use a stable positive approximation (focal weight * p*(1-p)).
        hess = a * term * p * (1.0 - p)
        hess = np.maximum(hess, 1e-6)
        grad = np.nan_to_num(grad, nan=0.0, posinf=1e3, neginf=-1e3)
        # silence the unused intermediate (kept for derivation clarity).
        _ = g
        return grad, hess

    return obj
