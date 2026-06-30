"""Generative tabular augmentation, rare-class only (DATA-11).

Blueprint Part 21.2 (l.810-811), Part 5.5 (l.207-208).

HARD CAVEAT (read before using):
    Naive tabular GANs/VAEs FAIL to preserve BEHAVIOURAL patterns — inter-event timing,
    velocity, and multi-account motifs — because they generate rows independently
    (2026 benchmarks; Part 5.5/21.2). Therefore:
      * Behavioural realism ONLY comes from the agent simulator (simulator.py).
      * Generative augmentation here is FEATURE-SPACE padding for the supervised (tabular)
        layer ONLY, applied to the MINORITY (fraud) class ONLY, anchored to the real/
        simulated minority distribution.
      * NEVER evaluate models on synthetic-only data. Calibration is ML's job; we only
        provide the augmented rows + imbalance hooks (negative subsampling 1:3-1:10 +
        class-weight handoff).

SDV (CTGAN/TVAE/diffusion) is OPTIONAL and guarded. The default is a pure numpy/pandas
fallback: rare-class oversampling by duplicating minority rows and adding small Gaussian
jitter to numeric columns (entity/categorical columns are preserved, not synthesised).
Deterministic from `seed`. Status: REAL on synthetic data.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:  # pragma: no cover - exercised only when SDV is installed
    from sdv.single_table import CTGANSynthesizer  # type: ignore  # noqa: F401

    HAVE_SDV = True
except Exception:
    HAVE_SDV = False


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def oversample_minority(
    df: pd.DataFrame,
    label_col: str,
    *,
    minority_value: object = True,
    target_ratio: float = 0.25,
    jitter_frac: float = 0.02,
    seed: int = 1405,
) -> pd.DataFrame:
    """Feature-space rare-class oversampling (numpy/pandas fallback).

    Duplicates minority rows with small Gaussian jitter on numeric columns until the
    minority class reaches `target_ratio` of the total. Categorical/entity columns are
    copied verbatim (we do NOT synthesise ids or behavioural sequences — see the caveat).

    Returns the augmented frame (original rows preserved, synthetic rows appended). The
    synthetic rows are tagged with a boolean column `__synthetic__` so they can be
    excluded from evaluation (never evaluate on synthetic-only).
    """
    rng = np.random.default_rng(seed)
    if label_col not in df.columns:
        raise KeyError(f"label_col {label_col!r} not in dataframe")

    out = df.copy()
    out["__synthetic__"] = False

    minority = out[out[label_col] == minority_value]
    if minority.empty:
        return out  # nothing to oversample

    n_total = len(out)
    n_min = len(minority)
    # how many minority rows we WANT after augmentation
    desired_min = int(np.ceil(target_ratio * n_total / (1 - target_ratio))) + n_min
    n_to_add = max(0, desired_min - n_min)
    if n_to_add == 0:
        return out

    num_cols = [c for c in _numeric_cols(minority) if c != label_col]
    stds = {c: float(minority[c].std(ddof=0) or 0.0) for c in num_cols}

    picks = rng.integers(0, n_min, size=n_to_add)
    synth = minority.iloc[picks].copy().reset_index(drop=True)
    for c in num_cols:
        if stds[c] > 0:
            noise = rng.normal(0.0, jitter_frac * stds[c], size=n_to_add)
            synth[c] = synth[c].to_numpy(dtype=float) + noise
    synth[label_col] = minority_value
    synth["__synthetic__"] = True

    return pd.concat([out, synth], ignore_index=True)


def negative_subsample(
    df: pd.DataFrame,
    label_col: str,
    *,
    minority_value: object = True,
    ratio: int = 5,
    seed: int = 1405,
) -> pd.DataFrame:
    """Imbalance hook: subsample the majority (negatives) to `ratio`:1 vs minority.

    Blueprint recommends 1:3-1:10 negative subsampling (default 1:5). Deterministic.
    """
    if not 3 <= ratio <= 10:
        # clamp to the blueprint-recommended band but do not crash
        ratio = min(10, max(3, ratio))
    rng = np.random.default_rng(seed)
    minority = df[df[label_col] == minority_value]
    majority = df[df[label_col] != minority_value]
    keep = min(len(majority), ratio * max(1, len(minority)))
    if keep >= len(majority):
        return df.copy()
    idx = rng.choice(len(majority), size=keep, replace=False)
    sub_majority = majority.iloc[np.sort(idx)]
    return pd.concat([minority, sub_majority], ignore_index=True)


def class_weights(df: pd.DataFrame, label_col: str,
                  minority_value: object = True) -> dict[object, float]:
    """Imbalance hook: inverse-frequency class weights for ML's class-weight/focal-loss.

    We only PROVIDE the weights; calibration/focal-loss is ML's responsibility.
    """
    n = max(1, len(df))
    n_min = max(1, int((df[label_col] == minority_value).sum()))
    n_maj = max(1, n - n_min)
    return {minority_value: n / (2 * n_min), "majority": n / (2 * n_maj)}


def augment(
    df: pd.DataFrame,
    label_col: str,
    *,
    minority_value: object = True,
    target_ratio: float = 0.25,
    seed: int = 1405,
    use_sdv: Optional[bool] = None,
) -> pd.DataFrame:
    """Top-level entry: feature-space minority augmentation.

    If SDV is installed and use_sdv is True, a CTGAN synthesiser could be wired here for
    the minority class only; otherwise (the default everywhere in this env) the pure
    numpy/pandas jitter-oversampler is used. Both are FEATURE-SPACE + MINORITY-CLASS only.
    """
    if use_sdv is None:
        use_sdv = HAVE_SDV
    # SDV path is intentionally a thin SCAFFOLD: it would train a CTGAN on the minority
    # rows in feature space only. We keep the fallback authoritative for reproducibility.
    return oversample_minority(
        df, label_col, minority_value=minority_value,
        target_ratio=target_ratio, seed=seed,
    )


def demo() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "amount": rng.normal(1000, 50, size=100),
        "is_fraud": [True] * 3 + [False] * 97,
    })
    return augment(df, "is_fraud", target_ratio=0.3, seed=0)
