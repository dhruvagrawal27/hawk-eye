"""Leakage-safe splits: time-based (past->future) and entity-disjoint (ML-2; Part 14, 20.4).

Fraud detection is a forecasting problem: splitting randomly leaks the future into the
past. These helpers split by **time** and by **entity**, and a guard rejects any split
that is effectively random. pandas-3.0-safe (``pd.api.types``, never ``np.issubdtype``).
"""
from __future__ import annotations

import hashlib
from typing import Iterator, Optional

import numpy as np
import pandas as pd


def _sortable_time(s: pd.Series) -> np.ndarray:
    """Coerce a timestamp-ish column to a sortable int64 array (pandas-3.0-safe)."""
    if pd.api.types.is_numeric_dtype(s):
        return s.to_numpy()
    try:
        return pd.to_datetime(s, utc=True, errors="raise").astype("int64").to_numpy()
    except Exception:
        return s.astype(str).to_numpy()


def temporal_split(df: pd.DataFrame, ts_col: str, test_frac: float = 0.25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train = past, test = future. Cut at the (1 - test_frac) quantile of time."""
    if ts_col not in df.columns:
        raise KeyError(f"ts_col {ts_col!r} not in {list(df.columns)}")
    if not 0.0 < test_frac < 1.0:
        raise ValueError("test_frac must be in (0,1)")
    order = _sortable_time(df[ts_col]).argsort(kind="stable")
    sorted_df = df.iloc[order].reset_index(drop=True)
    cut = max(1, min(int(round(len(sorted_df) * (1 - test_frac))), len(sorted_df) - 1))
    return sorted_df.iloc[:cut].reset_index(drop=True), sorted_df.iloc[cut:].reset_index(drop=True)


def is_temporal_split(train: pd.DataFrame, test: pd.DataFrame, ts_col: str) -> bool:
    """True iff max(train time) <= min(test time) — test strictly in the future."""
    if train.empty or test.empty:
        return False
    return _sortable_time(train[ts_col]).max() <= _sortable_time(test[ts_col]).min()


def assert_not_random_split(train: pd.DataFrame, test: pd.DataFrame, ts_col: str, tol_frac: float = 0.02) -> None:
    """Reject a split where >tol_frac of train rows are newer than the earliest test row."""
    tr = _sortable_time(train[ts_col])
    te = _sortable_time(test[ts_col])
    if tr.size == 0 or te.size == 0:
        return
    newer = float((tr > te.min()).mean())
    if newer > tol_frac:
        raise AssertionError(
            f"split looks random: {newer:.1%} of train is newer than earliest test "
            f"(tol {tol_frac:.1%}). Fraud data must be split by time."
        )


def _entity_bucket(entity: str, salt: str = "hawkeye-ml") -> float:
    h = hashlib.sha256(f"{salt}:{entity}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def entity_disjoint_split(
    df: pd.DataFrame, entity_col: str, test_frac: float = 0.25, seed: int = 1405
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """No entity appears in both train and test (prevents identity memorisation)."""
    if entity_col not in df.columns:
        raise KeyError(f"entity_col {entity_col!r} not in {list(df.columns)}")
    salt = f"hawkeye-ml-{seed}"
    buckets = df[entity_col].astype(str).map(lambda e: _entity_bucket(e, salt))
    test_mask = buckets < test_frac
    return df[~test_mask].reset_index(drop=True), df[test_mask].reset_index(drop=True)


def is_entity_disjoint(train: pd.DataFrame, test: pd.DataFrame, entity_col: str) -> bool:
    a = set(train[entity_col].astype(str)) if not train.empty else set()
    b = set(test[entity_col].astype(str)) if not test.empty else set()
    return len(a & b) == 0


def time_aware_cv(
    df: pd.DataFrame, ts_col: str, n_splits: int = 4, min_train_frac: float = 0.3
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window CV: each fold trains on the past, validates on the next block.

    Yields (train_idx, val_idx) into the time-sorted frame — used for L3 time-aware CV.
    """
    n = len(df)
    order = _sortable_time(df[ts_col]).argsort(kind="stable")
    start = int(n * min_train_frac)
    if start < 1 or start >= n:
        return
    block = max(1, (n - start) // n_splits)
    pos = start
    while pos < n:
        end = min(pos + block, n)
        if end <= pos:
            break
        yield order[:pos], order[pos:end]
        pos = end


def label_aware_temporal_split(
    df: pd.DataFrame, ts_col: str, label: pd.Series, test_frac: float = 0.25
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Temporal split that keeps a parallel label Series aligned to each part."""
    df2 = df.copy()
    df2["__label__"] = np.asarray(label).astype(int)
    tr, te = temporal_split(df2, ts_col, test_frac)
    return (
        tr.drop(columns="__label__"),
        tr["__label__"].reset_index(drop=True),
        te.drop(columns="__label__"),
        te["__label__"].reset_index(drop=True),
    )
