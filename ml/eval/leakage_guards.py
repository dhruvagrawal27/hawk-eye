"""Leakage + eval-rigor guards (ML-2; blueprint Part 14, 20.0).

Catches the four evaluation pitfalls (Part 14):
  1. data leakage      -> ``detect_leaky_features`` / ``remove_leaky_features``
  2. temporal leakage  -> enforced by ``ml.eval.splits`` (time-based) + ``assert_no_future_feature``
  3. point-adjust      -> impossible by construction (``ml.eval.metrics`` has no PA); ``assert_no_point_adjust``
  4. synthetic-only    -> ``synthetic_only_guard`` documents the limitation explicitly
pandas-3.0-safe (uses ``pd.api.types``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd

import ml.eval.metrics as _metrics


def detect_leaky_features(
    df: pd.DataFrame,
    label_col: str,
    known_leaky: Optional[Iterable[str]] = None,
    corr_threshold: float = 0.95,
    predictor_threshold: float = 0.99,
) -> dict[str, str]:
    """Return {column: reason} for features that leak the label.

    Flags: (a) explicitly-known leaky columns; (b) |Pearson corr| >= corr_threshold;
    (c) a single feature that predicts the label with >= predictor_threshold accuracy
    via an optimal threshold (numeric) or category->label map (categorical).
    """
    if label_col not in df.columns:
        raise KeyError(f"label_col {label_col!r} not in {list(df.columns)}")
    y = pd.to_numeric(df[label_col], errors="coerce").fillna(0).astype(int).to_numpy()
    leaky: dict[str, str] = {}
    known = set(known_leaky or [])
    for col in df.columns:
        if col == label_col:
            continue
        if col in known:
            leaky[col] = "explicitly known leaky"
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            x = pd.to_numeric(s, errors="coerce").fillna(0.0).to_numpy()
            if np.std(x) > 0 and np.std(y) > 0:
                corr = abs(float(np.corrcoef(x, y)[0, 1]))
                if corr >= corr_threshold:
                    leaky[col] = f"|corr|={corr:.3f} >= {corr_threshold}"
                    continue
            if _best_threshold_accuracy(x, y) >= predictor_threshold:
                leaky[col] = f"single-feature threshold predicts label >= {predictor_threshold}"
        else:
            if _category_map_accuracy(s.astype(str).to_numpy(), y) >= predictor_threshold:
                leaky[col] = f"category->label map predicts >= {predictor_threshold}"
    return leaky


def remove_leaky_features(
    df: pd.DataFrame, label_col: str, known_leaky: Optional[Iterable[str]] = None
) -> pd.DataFrame:
    """Drop detected leaky features (keeps the label column)."""
    leaky = detect_leaky_features(df, label_col, known_leaky)
    return df.drop(columns=[c for c in leaky if c in df.columns])


def _balanced_accuracy(pred: np.ndarray, y: np.ndarray) -> float:
    """Mean of per-class recall — robust to extreme imbalance (all-zero -> 0.5, not ~0.99)."""
    p = float((y == 1).sum())
    n = float((y == 0).sum())
    if p == 0 or n == 0:
        return 0.0
    tpr = float(((pred == 1) & (y == 1)).sum()) / p
    tnr = float(((pred == 0) & (y == 0)).sum()) / n
    return 0.5 * (tpr + tnr)


def _best_threshold_accuracy(x: np.ndarray, y: np.ndarray) -> float:
    """Best BALANCED accuracy of a single-feature threshold rule (both polarities)."""
    if x.size == 0 or len(np.unique(y)) < 2:
        return 0.0
    qs = np.quantile(x, np.linspace(0.05, 0.95, 19))
    best = 0.0
    for t in np.unique(qs):
        for pred in ((x >= t).astype(int), (x < t).astype(int)):
            best = max(best, _balanced_accuracy(pred, y))
    return best


def _category_map_accuracy(x: np.ndarray, y: np.ndarray) -> float:
    """BALANCED accuracy of a category->majority-label map (robust to imbalance)."""
    if x.size == 0 or len(np.unique(y)) < 2:
        return 0.0
    df = pd.DataFrame({"x": x, "y": y})
    mapping = df.groupby("x")["y"].agg(lambda s: int(round(s.mean())))
    pred = df["x"].map(mapping).to_numpy()
    return _balanced_accuracy(pred, y)


def assert_no_future_feature(df: pd.DataFrame, ts_col: str, feature_cols: Iterable[str]) -> None:
    """Heuristic temporal-leakage guard: a feature must not be perfectly time-ordered
    with the row time in a way that implies it was computed from the future."""
    if ts_col not in df.columns:
        return
    order = pd.to_datetime(df[ts_col], utc=True, errors="coerce").rank(method="first").to_numpy()
    for col in feature_cols:
        if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
            continue
        x = pd.to_numeric(df[col], errors="coerce").fillna(0.0).to_numpy()
        if np.std(x) == 0:
            continue
        # A feature that is a near-perfect *future* index (corr with reverse-time ~ 1).
        corr = abs(float(np.corrcoef(x, -order)[0, 1])) if np.std(order) > 0 else 0.0
        if corr >= 0.999:
            raise AssertionError(f"feature {col!r} appears future-derived (corr with reverse-time {corr:.3f})")


def assert_no_point_adjust() -> None:
    """Fail loudly if point-adjust ever gets enabled (it must not exist)."""
    if getattr(_metrics, "POINT_ADJUST_ENABLED", False):
        raise AssertionError("point-adjust must never be enabled (Part 14)")
    if hasattr(_metrics, "point_adjust"):
        raise AssertionError("a point_adjust() function exists — remove it (Part 14)")


@dataclass
class SyntheticOnlyGuard:
    """Documents the synthetic-only limitation (Part 14 pitfall #4)."""

    message: str = (
        "Evaluation is on SYNTHETIC + public benchmark data only. Synthetic validates "
        "training/augmentation and relative model comparison, but absolute detection "
        "quality MUST be confirmed on real labelled outcomes before production claims."
    )
    acknowledged: bool = True

    def to_dict(self) -> dict:
        return {"synthetic_only": True, "message": self.message, "acknowledged": self.acknowledged}


def synthetic_only_guard() -> SyntheticOnlyGuard:
    return SyntheticOnlyGuard()
