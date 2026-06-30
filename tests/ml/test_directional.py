"""Directional-expectation CI suite (ML-28; blueprint Part 31).

The blueprint's canonical directional relation: an event that is OFF-HOURS, to a
NEW BENEFICIARY, for a HIGH VALUE should raise risk MONOTONICALLY as those risk
factors are toggled on. We assert this on a REAL fitted L3 scorer two ways:

  * per-factor: toggling off-hours ON, and new-beneficiary ON, each raises mean risk
    (decreases are rare and negligible -> the model points the right way);
  * cumulative: base  <=  +off-hours  <=  +new-beneficiary  <=  +high-value, where each
    step's MEAN risk is non-decreasing (a GBDT is not monotone-constrained, so the
    directional law is read at the population mean, with a tiny numerical tolerance).

Uses only the LightGBM/sklearn-backed L3 scorer -> no torch in this process.

Run: .mlvenv/bin/python -m pytest tests/ml/test_directional.py -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.adapters import DataSimFeatureSource
from ml.layers.l3 import LightGBMScorer

# Mean risk may dip by at most this (tree-step noise) and still count as "non-decreasing".
MEAN_TOL = 5e-3


@pytest.fixture(scope="module")
def ctx():
    src = DataSimFeatureSource()
    X, y = src.supervised_xy()
    ts = src.events().set_index("event_id")["ts"].reindex(X.index)
    order = pd.to_datetime(ts, utc=True).argsort().to_numpy()
    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    assert int(y.sum()) >= 5
    scorer = LightGBMScorer(n_estimators=300)
    scorer.fit(X, y)

    # A clean BENIGN baseline batch: on-hours, no new beneficiary, modest amount.
    benign = X[y.to_numpy() == 0].reset_index(drop=True)
    rng = np.random.default_rng(1405)
    idx = rng.choice(len(benign), size=min(120, len(benign)), replace=False)
    base = benign.iloc[idx].reset_index(drop=True).copy()
    for col, val in (
        ("is_off_hours", 0),
        ("hour", 11),
        ("is_weekend", 0),
        ("new_beneficiary", 0),
    ):
        if col in base.columns:
            base[col] = val
    high_value = float(X["amount"].quantile(0.99))
    return scorer, X, base, high_value


def _set(df: pd.DataFrame, **overrides) -> pd.DataFrame:
    d = df.copy()
    for k, v in overrides.items():
        if k in d.columns:
            d[k] = v
    return d


# --------------------------------------------------------------------------- #
# per-factor: each individual risk factor points risk UP                       #
# --------------------------------------------------------------------------- #
def test_off_hours_raises_risk(ctx):
    scorer, _, base, _ = ctx
    b0 = scorer.predict_proba(base)
    off = scorer.predict_proba(_set(base, is_off_hours=1, hour=2))
    assert off.mean() > b0.mean(), "off-hours must raise mean risk"
    assert (
        float((off < b0 - 1e-6).mean()) <= 0.05
    ), "off-hours lowered risk for too many rows"


def test_new_beneficiary_raises_risk(ctx):
    scorer, _, base, _ = ctx
    b0 = scorer.predict_proba(base)
    bene = scorer.predict_proba(_set(base, new_beneficiary=1, has_beneficiary=1))
    assert bene.mean() > b0.mean(), "a new beneficiary must raise mean risk"
    assert (
        float((bene < b0 - 1e-6).mean()) <= 0.05
    ), "new-beneficiary lowered risk for too many rows"


# --------------------------------------------------------------------------- #
# cumulative: off-hours + new-bene + high-value is MONOTONE non-decreasing      #
# --------------------------------------------------------------------------- #
def test_cumulative_risk_factors_are_monotone(ctx):
    scorer, _, base, high_value = ctx

    s0 = scorer.predict_proba(base).mean()
    s1 = scorer.predict_proba(_set(base, is_off_hours=1, hour=2)).mean()
    s2 = scorer.predict_proba(
        _set(base, is_off_hours=1, hour=2, new_beneficiary=1, has_beneficiary=1)
    ).mean()
    s3 = scorer.predict_proba(
        _set(
            base,
            is_off_hours=1,
            hour=2,
            new_beneficiary=1,
            has_beneficiary=1,
            amount=high_value,
            log1p_amount=float(np.log1p(high_value)),
        )
    ).mean()

    stages = [("base", s0), ("+off_hours", s1), ("+new_bene", s2), ("+high_value", s3)]
    for (pname, prev), (cname, cur) in zip(stages, stages[1:]):
        assert (
            cur >= prev - MEAN_TOL
        ), f"risk DROPPED going {pname}({prev:.3f}) -> {cname}({cur:.3f}) (directional law violated)"
    # End-to-end: the fully off-hours/new-bene/high-value event is clearly riskier than baseline.
    assert (
        s3 > s0 + 0.05
    ), f"full risk profile ({s3:.3f}) must exceed benign baseline ({s0:.3f})"
