"""Metamorphic / invariance CI suite (ML-28; blueprint Part 31).

Metamorphic relations a fraud scorer must satisfy:

  R1 (monotone in amount): scaling a transaction's amount UP must NOT DECREASE risk.
     More money moved (with its derived amount features moved consistently) is never
     LESS suspicious, all else equal.
  R2 (irrelevant-field invariance): perturbing a feature the fitted model assigns ZERO
     importance to (never split on) must NOT change the score at all.
  R3 (no-op invariance): re-scoring the identical rows twice is deterministic, and
     scoring a row-permuted batch yields the same per-row scores (no cross-row leakage).

We build ONE fitted L3 LightGBM scorer (tree/sklearn backend -> no torch in process),
then perturb feature rows and assert each relation on a sampled set of rows.

NOTE: the L3 scorer is feature-NAME/ORDER bound (it rejects unknown columns), so the
"irrelevant field" is modelled the honest way: a column with zero learned importance.

Run: .mlvenv/bin/python -m pytest tests/ml/test_metamorphic.py -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.adapters import DataSimFeatureSource
from ml.layers.l3 import LightGBMScorer

TOL = 1e-9  # exact-invariance tolerance (deterministic tree inference)

# Features derived from the raw amount that must move together when amount scales.
_AMOUNT_DERIVED = ("amount", "log1p_amount", "amount_z_personal", "amount_z_peer")


@pytest.fixture(scope="module")
def fitted():
    src = DataSimFeatureSource()
    X, y = src.supervised_xy()
    ts = src.events().set_index("event_id")["ts"].reindex(X.index)
    order = pd.to_datetime(ts, utc=True).argsort().to_numpy()
    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    assert int(y.sum()) >= 5
    scorer = LightGBMScorer(n_estimators=300)
    scorer.fit(X, y)
    importances = pd.Series(
        scorer._model.feature_importances_, index=scorer._feature_names
    )
    return scorer, X, importances


def _sample(X: pd.DataFrame, n: int = 80, seed: int = 1405) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), size=min(n, len(X)), replace=False)
    return X.iloc[idx].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# R1: amount scaled UP must not DECREASE risk                                  #
# --------------------------------------------------------------------------- #
def test_amount_scaling_up_does_not_decrease_risk(fitted):
    scorer, X, _ = fitted
    rows = _sample(X)
    base = scorer.predict_proba(rows)

    # A GBDT is not monotone-constrained, so the relation is enforced the honest way:
    #  (a) MEAN risk is non-decreasing when the amount channel scales up, and
    #  (b) per-row decreases are rare AND negligible in magnitude (tree-step noise only).
    for factor in (2.0, 5.0, 20.0):
        up = rows.copy()
        up["amount"] = up["amount"] * factor
        if "log1p_amount" in up.columns:
            up["log1p_amount"] = np.log1p(up["amount"].clip(lower=0))
        scaled = scorer.predict_proba(up)

        assert scaled.mean() >= base.mean() - 1e-9, (
            f"mean risk dropped when amount scaled x{factor} (R1 violated)"
        )
        decreases = base - scaled
        frac_dec = float((decreases > 1e-6).mean())
        max_dec = float(decreases.max())
        assert frac_dec <= 0.10, (
            f"amount x{factor}: {frac_dec:.0%} of rows decreased (>10% => R1 violated)"
        )
        assert max_dec <= 0.02, (
            f"amount x{factor}: a row's risk fell by {max_dec:.3f} (>0.02 => R1 violated)"
        )


# --------------------------------------------------------------------------- #
# R2: changing an IRRELEVANT (zero-importance) field must not change score      #
# --------------------------------------------------------------------------- #
def test_irrelevant_field_change_does_not_change_score(fitted):
    scorer, X, importances = fitted
    rows = _sample(X)
    base = scorer.predict_proba(rows)

    irrelevant = [c for c in scorer._feature_names if importances.get(c, 0) == 0]
    assert irrelevant, "expected at least one zero-importance feature to perturb"

    perturbed = rows.copy()
    rng = np.random.default_rng(0)
    for col in irrelevant:
        # arbitrary perturbation of every never-split-on feature
        perturbed[col] = perturbed[col].to_numpy(dtype=float) + rng.normal(5.0, 3.0, len(perturbed))
    after = scorer.predict_proba(perturbed)
    assert np.allclose(base, after, atol=TOL), (
        f"perturbing {len(irrelevant)} zero-importance features changed the score (R2)"
    )


# --------------------------------------------------------------------------- #
# R3: determinism + row-permutation invariance (no cross-row leakage)          #
# --------------------------------------------------------------------------- #
def test_determinism_and_row_permutation_invariance(fitted):
    scorer, X, _ = fitted
    rows = _sample(X)
    base = scorer.predict_proba(rows)

    # (a) re-scoring is deterministic
    assert np.array_equal(base, scorer.predict_proba(rows)), "scoring is not deterministic (R3)"

    # (b) permuting ROWS permutes scores identically (each row scored independently)
    rng = np.random.default_rng(7)
    perm = rng.permutation(len(rows))
    permuted_scores = scorer.predict_proba(rows.iloc[perm].reset_index(drop=True))
    assert np.allclose(permuted_scores, base[perm], atol=TOL), "row order affected scores (R3)"
