"""Leakage-safe dataset splits (DATA-24).

Blueprint Part 21.4 (splits & leakage avoidance) and Part 14 (leakage pitfalls, l.475-479).
Status: REAL (pure numpy/pandas).

Three guarantees ML depends on to train honestly:
1. TEMPORAL split -- train on the PAST, validate/test on the FUTURE. NEVER a random split
   for fraud data (random splits leak the future into training and inflate metrics).
2. ENTITY-DISJOINT split -- no employee/entity appears in both train and test (otherwise the
   model memorises the entity, not the behaviour).
3. LEAKY-FEATURE REMOVAL -- drop fields that encode the label (e.g. PaySim balance columns;
   any near-perfect single-feature predictor). A leakage detector finds them.

`assert_not_random_split` is the guard the acceptance test calls to REJECT a random split.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# 1. Temporal split                                                            #
# --------------------------------------------------------------------------- #
def temporal_split(
    df: pd.DataFrame, ts_col: str, test_frac: float = 0.25
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train = past, test = future. Sorts by `ts_col`, cuts at the (1-test_frac) quantile.

    Every test-set timestamp is >= every train-set timestamp (no future leakage).
    """
    if ts_col not in df.columns:
        raise KeyError(f"ts_col {ts_col!r} not in dataframe columns {list(df.columns)}")
    if not 0.0 < test_frac < 1.0:
        raise ValueError("test_frac must be in (0,1)")
    order = _sortable(df[ts_col])
    ranks = order.argsort(kind="stable")
    sorted_df = df.iloc[ranks].reset_index(drop=True)
    cut = int(round(len(sorted_df) * (1.0 - test_frac)))
    cut = max(1, min(cut, len(sorted_df) - 1)) if len(sorted_df) > 1 else len(sorted_df)
    train = sorted_df.iloc[:cut].reset_index(drop=True)
    test = sorted_df.iloc[cut:].reset_index(drop=True)
    return train, test


def _sortable(s: pd.Series) -> np.ndarray:
    """Coerce a timestamp-ish column to a sortable numeric/datetime array."""
    if np.issubdtype(s.dtype, np.number):
        return s.to_numpy()
    try:
        return pd.to_datetime(s, utc=True, errors="raise").astype("int64").to_numpy()
    except Exception:
        return s.astype(str).to_numpy()


def is_temporal_split(
    train: pd.DataFrame, test: pd.DataFrame, ts_col: str
) -> bool:
    """True iff max(train ts) <= min(test ts) -- i.e. test is strictly in the future."""
    if train.empty or test.empty:
        return False
    tr = _sortable(train[ts_col])
    te = _sortable(test[ts_col])
    return tr.max() <= te.min()


# --------------------------------------------------------------------------- #
# 2. Entity-disjoint split                                                     #
# --------------------------------------------------------------------------- #
def entity_disjoint_split(
    df: pd.DataFrame, entity_col: str, test_frac: float = 0.25, seed: int = 1405
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partition by ENTITY so no entity appears in both splits (deterministic by seed)."""
    if entity_col not in df.columns:
        raise KeyError(f"entity_col {entity_col!r} not in {list(df.columns)}")
    rng = np.random.default_rng(seed)
    entities = pd.unique(df[entity_col])
    rng.shuffle(entities)
    n_test = max(1, int(round(len(entities) * test_frac)))
    test_entities = set(entities[:n_test].tolist())
    test_mask = df[entity_col].isin(test_entities)
    train = df.loc[~test_mask].reset_index(drop=True)
    test = df.loc[test_mask].reset_index(drop=True)
    return train, test


def is_entity_disjoint(
    train: pd.DataFrame, test: pd.DataFrame, entity_col: str
) -> bool:
    return not (set(train[entity_col]) & set(test[entity_col]))


# --------------------------------------------------------------------------- #
# 3. Leaky-feature detection & removal                                         #
# --------------------------------------------------------------------------- #
def detect_leaky_features(
    df: pd.DataFrame,
    label_col: str,
    known_leaky: Iterable[str] = (),
    corr_threshold: float = 0.95,
    predictor_threshold: float = 0.99,
) -> dict[str, str]:
    """Find columns that encode the label. Returns {column: reason}.

    Detectors:
    - explicitly-known leaky columns (e.g. PaySim balance columns passed by the caller);
    - |Pearson corr with label| >= corr_threshold (numeric);
    - single-feature near-perfect predictor: a threshold split (numeric) or a category->label
      mapping (categorical) that classifies >= predictor_threshold of rows correctly.
    """
    if label_col not in df.columns:
        raise KeyError(f"label_col {label_col!r} not in {list(df.columns)}")
    y = df[label_col]
    yv = pd.to_numeric(y, errors="coerce")
    leaky: dict[str, str] = {}
    known = set(known_leaky)

    for col in df.columns:
        if col == label_col:
            continue
        if col in known:
            leaky[col] = "known-leaky (caller-supplied; e.g. PaySim balance column)"
            continue
        series = df[col]
        if pd.api.types.is_numeric_dtype(series) and yv.notna().all():
            x = pd.to_numeric(series, errors="coerce")
            if x.notna().all() and x.nunique() > 1 and yv.nunique() > 1:
                corr = abs(np.corrcoef(x.to_numpy(float), yv.to_numpy(float))[0, 1])
                if np.isnan(corr):
                    corr = 0.0
                if corr >= corr_threshold:
                    leaky[col] = f"corr_with_label={corr:.3f} >= {corr_threshold}"
                    continue
                acc = _best_threshold_accuracy(x.to_numpy(float), yv.to_numpy(int))
                if acc >= predictor_threshold:
                    leaky[col] = f"single-feature threshold predictor acc={acc:.3f}"
                    continue
        else:
            # categorical: map each category to its majority label, measure accuracy
            if yv.notna().all() and series.nunique() > 1:
                acc = _category_map_accuracy(series, yv.astype(int))
                if acc >= predictor_threshold:
                    leaky[col] = f"category->label map acc={acc:.3f}"
    return leaky


def _best_threshold_accuracy(x: np.ndarray, y: np.ndarray) -> float:
    """Best accuracy over all single-threshold splits of x predicting y in {0,1}."""
    n = len(y)
    if n == 0:
        return 0.0
    order = np.argsort(x, kind="stable")
    xs, ys = x[order], y[order]
    total_pos = ys.sum()
    total_neg = n - total_pos
    # candidate: predict positive if x > t. Sweep cumulative.
    best = max(total_pos, total_neg) / n  # trivial baseline
    cum_pos = np.cumsum(ys)            # positives at or below each index
    cum_neg = np.cumsum(1 - ys)
    for i in range(n):
        # split after index i: left = <=, right = >
        left_pos, left_neg = cum_pos[i], cum_neg[i]
        right_pos = total_pos - left_pos
        right_neg = total_neg - left_neg
        # orientation A: right=positive
        accA = (right_pos + left_neg) / n
        # orientation B: left=positive
        accB = (left_pos + right_neg) / n
        best = max(best, accA, accB)
    return float(best)


def _category_map_accuracy(series: pd.Series, y: pd.Series) -> float:
    df = pd.DataFrame({"c": series.astype(str).values, "y": y.values})
    # each category predicts its majority label
    maj = df.groupby("c")["y"].agg(lambda s: s.value_counts().idxmax())
    pred = df["c"].map(maj)
    return float((pred.values == df["y"].values).mean())


def remove_leaky_features(
    df: pd.DataFrame,
    label_col: str,
    known_leaky: Iterable[str] = (),
    corr_threshold: float = 0.95,
    predictor_threshold: float = 0.99,
    return_report: bool = False,
):
    """Drop columns that encode the label; keep `label_col`. Returns the cleaned df
    (and the {col: reason} report if `return_report`)."""
    report = detect_leaky_features(
        df, label_col, known_leaky, corr_threshold, predictor_threshold
    )
    cleaned = df.drop(columns=list(report.keys()))
    if return_report:
        return cleaned, report
    return cleaned


# --------------------------------------------------------------------------- #
# 4. Random-split guard (REJECT random splits for fraud data)                  #
# --------------------------------------------------------------------------- #
def assert_not_random_split(
    train: pd.DataFrame, test: pd.DataFrame, ts_col: str, tol_frac: float = 0.02
) -> None:
    """Raise if the split is NOT temporal (i.e. looks random/interleaved).

    A temporal split has max(train ts) <= min(test ts). A random split interleaves
    timestamps, so a non-trivial fraction of train rows are newer than the earliest test
    row. This is the guard the acceptance test uses to reject a random split for fraud data.
    """
    if train.empty or test.empty:
        raise ValueError("empty split")
    tr = _sortable(train[ts_col])
    te = _sortable(test[ts_col])
    test_min = te.min()
    leaked = float((tr > test_min).mean())
    if leaked > tol_frac:
        raise AssertionError(
            f"random/leaky split rejected: {leaked:.1%} of train rows are newer than the "
            f"earliest test row (> {tol_frac:.1%}); use temporal_split() for fraud data "
            f"(Part 21.4 / Part 14)."
        )


def make_random_split(
    df: pd.DataFrame, test_frac: float = 0.25, seed: int = 1405
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deliberately-WRONG random split, provided so tests can prove the guard rejects it."""
    rng = np.random.default_rng(seed)
    idx = np.arange(len(df))
    rng.shuffle(idx)
    cut = int(round(len(df) * (1.0 - test_frac)))
    train = df.iloc[idx[:cut]].reset_index(drop=True)
    test = df.iloc[idx[cut:]].reset_index(drop=True)
    return train, test


def demo() -> pd.DataFrame:
    """Tiny ordered frame with an injected leaky column, for tests."""
    rng = np.random.default_rng(1405)
    n = 40
    y = (rng.random(n) < 0.3).astype(int)
    return pd.DataFrame({
        "ts": pd.date_range("2024-01-01", periods=n, freq="h").astype(str),
        "entity": [f"EMP-{i % 6:02d}" for i in range(n)],
        "amount": rng.gamma(2.0, 50.0, n),
        "leaky_balance": y.astype(float),  # encodes the label exactly
        "label": y,
    })
