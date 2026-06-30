"""Model-regression CI suite (ML-28; blueprint Part 31).

A model must NOT regress on a fixed eval set or on previously-caught cases. We pin a
quality FLOOR on the DATA-sim eval set under a FIXED seed + fixed temporal split:

  * AUPRC on the held-out (future) slice must clear a pinned floor (and trounce the
    base prevalence — the AP of a random ranker);
  * a set of previously-caught "champion" fraud cases must still be caught: their mean
    score stays in the top band and recall on them holds at a pinned floor.

Honest eval: split is PAST -> FUTURE (never random), no point-adjust. Tree/sklearn
backend only -> no torch in this process.

The floors are intentionally conservative (well below the observed value) so the gate
fires on a REAL regression, not on benign run-to-run noise.

Run: .mlvenv/bin/python -m pytest tests/ml/test_regression.py -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.adapters import DataSimFeatureSource
from ml.eval import average_precision, is_temporal_split, precision_at_k
from ml.layers.l3 import LightGBMScorer

# --- pinned regression floors (the build fails if a change drops below these) --- #
AUPRC_FLOOR = 0.12  # observed ~0.29 on the s1405 sim; floor = strong-vs-noise margin
PRECISION_AT_K_FLOOR = (
    0.10  # observed ~0.14 at k=2x positives; floor >> 0.011 prevalence
)
KNOWN_CASE_RECALL_FLOOR = 0.5  # previously-caught cases must stay caught
SEED = 1405
TEST_FRAC = 0.25


@pytest.fixture(scope="module")
def split():
    src = DataSimFeatureSource()
    X, y = src.supervised_xy()
    ts = src.events().set_index("event_id")["ts"].reindex(X.index)
    order = pd.to_datetime(ts, utc=True).argsort().to_numpy()
    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    ts_sorted = pd.Series(np.asarray(ts)[order], name="ts")

    n = len(X)
    cut = max(1, int(round(n * (1 - TEST_FRAC))))
    Xtr, ytr = X.iloc[:cut].reset_index(drop=True), y.iloc[:cut].reset_index(drop=True)
    Xte, yte = X.iloc[cut:].reset_index(drop=True), y.iloc[cut:].reset_index(drop=True)
    tr_ts = ts_sorted.iloc[:cut].reset_index(drop=True)
    te_ts = ts_sorted.iloc[cut:].reset_index(drop=True)
    # Honest split: test strictly in the FUTURE relative to train.
    assert is_temporal_split(
        pd.DataFrame({"ts": tr_ts}), pd.DataFrame({"ts": te_ts}), "ts"
    ), "eval split must be past -> future"
    assert int(yte.sum()) >= 3, "need positives in the eval slice"
    return Xtr, ytr, Xte, yte


@pytest.fixture(scope="module")
def scored(split):
    Xtr, ytr, Xte, yte = split
    scorer = LightGBMScorer(n_estimators=400, random_state=SEED)
    scorer.fit(Xtr, ytr)
    p = scorer.predict_proba(Xte)
    return yte.to_numpy(), p


def test_auprc_floor_holds(scored):
    yte, p = scored
    ap = average_precision(yte, p)
    prevalence = float(yte.mean())
    assert (
        ap > prevalence
    ), f"AUPRC {ap:.4f} must beat random prevalence {prevalence:.4f}"
    assert (
        ap >= AUPRC_FLOOR
    ), f"REGRESSION: eval AUPRC {ap:.4f} fell below pinned floor {AUPRC_FLOOR}"


def test_precision_at_k_floor_holds(scored):
    yte, p = scored
    k = max(1, int(yte.sum()) * 2)  # ~2x positives alert budget
    pk = precision_at_k(yte, p, k)
    assert (
        pk >= PRECISION_AT_K_FLOOR
    ), f"REGRESSION: precision@{k} {pk:.3f} below floor {PRECISION_AT_K_FLOOR}"


def test_previously_caught_cases_stay_caught(scored):
    """Pin recall on the known fraud cases at a top-decile operating threshold."""
    yte, p = scored
    known = np.flatnonzero(yte == 1)
    assert known.size > 0
    thr = float(
        np.quantile(p, 1.0 - TEST_FRAC)
    )  # operating point near the alert budget
    recall_known = float((p[known] >= thr).mean())
    assert recall_known >= KNOWN_CASE_RECALL_FLOOR, (
        f"REGRESSION: recall on previously-caught cases {recall_known:.2f} "
        f"below floor {KNOWN_CASE_RECALL_FLOOR}"
    )
    # Known-fraud scores sit well above the benign median (no silent decay).
    benign_median = float(np.median(p[yte == 0]))
    assert float(np.median(p[known])) > benign_median


def test_eval_is_deterministic_under_fixed_seed(split):
    """Re-fitting with the same seed/split reproduces the AUPRC bit-for-bit (repro gate)."""
    Xtr, ytr, Xte, yte = split
    aps = []
    for _ in range(2):
        s = LightGBMScorer(n_estimators=400, random_state=SEED)
        s.fit(Xtr, ytr)
        aps.append(average_precision(yte.to_numpy(), s.predict_proba(Xte)))
    assert aps[0] == pytest.approx(
        aps[1], abs=1e-9
    ), "fixed-seed eval must be reproducible"
