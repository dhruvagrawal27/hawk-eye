"""Production drift + data-integrity CI suite (ML-28; blueprint Part 27/31).

Two guards a serving pipeline needs:

  * DATA INTEGRITY: incoming feature batches match the trained schema (same columns),
    sit inside expected ranges, and carry no NULLs in required features. A batch with a
    missing column / out-of-range value / injected null is FLAGGED.
  * DISTRIBUTION DRIFT: the Population Stability Index (PSI) fires on a deliberately
    shifted batch but stays quiet on an in-distribution batch. PSI is computed INLINE
    here (``ml.mlops.drift`` is not present in this build); if/when that module lands,
    swap the inline ``population_stability_index`` for the import.

Pure pandas/numpy -> no heavy model, no torch. pandas-3.0-safe (``pd.api.types``).

Run: .mlvenv/bin/python -m pytest tests/ml/test_drift_integrity.py -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.adapters import DataSimFeatureSource

# Conventional PSI bands (Siddiqi): <0.1 stable, 0.1-0.25 moderate shift, >0.25 significant.
PSI_ALERT = 0.25


# --------------------------------------------------------------------------- #
# inline PSI (drop-in for ml.mlops.drift.population_stability_index)            #
# --------------------------------------------------------------------------- #
def population_stability_index(
    reference: np.ndarray, current: np.ndarray, n_bins: int = 10, eps: float = 1e-6
) -> float:
    """PSI between a reference and current 1-D sample using reference quantile bins."""
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)
    # Quantile edges from the reference; widen the outer edges to catch tail mass.
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, n_bins + 1)))
    if edges.size < 2:
        return 0.0
    edges[0], edges[-1] = -np.inf, np.inf
    ref_pct = np.histogram(ref, bins=edges)[0] / max(len(ref), 1)
    cur_pct = np.histogram(cur, bins=edges)[0] / max(len(cur), 1)
    ref_pct = np.clip(ref_pct, eps, None)
    cur_pct = np.clip(cur_pct, eps, None)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


# --------------------------------------------------------------------------- #
# lightweight schema / integrity checker                                       #
# --------------------------------------------------------------------------- #
def check_integrity(
    batch: pd.DataFrame,
    schema: list[str],
    ranges: dict[str, tuple[float, float]],
    required_non_null: list[str],
) -> list[str]:
    """Return a list of integrity violations (empty == clean)."""
    violations: list[str] = []
    missing = [c for c in schema if c not in batch.columns]
    if missing:
        violations.append(f"missing_columns:{missing}")
    extra = [c for c in batch.columns if c not in schema]
    if extra:
        violations.append(f"unexpected_columns:{extra}")
    for col, (lo, hi) in ranges.items():
        if col in batch.columns and pd.api.types.is_numeric_dtype(batch[col]):
            x = pd.to_numeric(batch[col], errors="coerce")
            if float(x.min()) < lo or float(x.max()) > hi:
                violations.append(f"out_of_range:{col}")
    for col in required_non_null:
        if col not in batch.columns or batch[col].isna().any():
            violations.append(f"null_in_required:{col}")
    return violations


@pytest.fixture(scope="module")
def reference():
    src = DataSimFeatureSource()
    X, _ = src.supervised_xy()
    return X.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# data integrity                                                               #
# --------------------------------------------------------------------------- #
def test_clean_batch_passes_integrity(reference):
    schema = list(reference.columns)
    ranges = {"is_off_hours": (0, 1), "amount": (0, float(reference["amount"].max()) * 2)}
    required = ["amount", "is_off_hours"]
    assert check_integrity(reference, schema, ranges, required) == []


def test_integrity_flags_missing_column_range_and_null(reference):
    schema = list(reference.columns)
    ranges = {"is_off_hours": (0, 1), "amount": (0, float(reference["amount"].max()))}
    required = ["amount", "is_off_hours"]

    # (a) missing a schema column
    miss = reference.drop(columns=["amount"])
    assert any(v.startswith("missing_columns") for v in check_integrity(miss, schema, ranges, required))

    # (b) out-of-range value (off-hours flag should be 0/1; inject a 9)
    bad_range = reference.copy()
    bad_range.loc[bad_range.index[0], "is_off_hours"] = 9
    assert any(v == "out_of_range:is_off_hours" for v in check_integrity(bad_range, schema, ranges, required))

    # (c) null in a required feature
    nulls = reference.copy()
    nulls.loc[nulls.index[0], "amount"] = np.nan
    assert any(v == "null_in_required:amount" for v in check_integrity(nulls, schema, ranges, required))


# --------------------------------------------------------------------------- #
# distribution drift (PSI)                                                      #
# --------------------------------------------------------------------------- #
def test_psi_quiet_on_in_distribution_batch(reference):
    amt = reference["amount"].to_numpy(dtype=float)
    half1 = amt[: len(amt) // 2]
    half2 = amt[len(amt) // 2 :]
    psi = population_stability_index(half1, half2)
    assert psi < PSI_ALERT, f"PSI {psi:.3f} false-fired on an in-distribution split"


def test_psi_fires_on_shifted_batch(reference):
    amt = reference["amount"].to_numpy(dtype=float)
    # Shift the current batch: 10x the amounts (a population-level amount shift).
    shifted = amt * 10.0 + 1_000_000.0
    psi = population_stability_index(amt, shifted)
    assert psi >= PSI_ALERT, f"PSI {psi:.3f} failed to fire on a clearly shifted batch"


def test_psi_monotone_with_shift_magnitude(reference):
    amt = reference["amount"].to_numpy(dtype=float)
    small = population_stability_index(amt, amt + amt.std() * 0.5)
    large = population_stability_index(amt, amt + amt.std() * 5.0)
    assert large >= small, "PSI should not shrink as the shift grows"
