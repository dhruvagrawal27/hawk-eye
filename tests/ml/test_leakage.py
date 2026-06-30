"""Eval-rigor / leakage CI suite (ML-28; blueprint Part 14, 20.0/31).

Locks down the four evaluation pitfalls the blueprint forbids:

  1. point-adjust       -> ``ml.eval.POINT_ADJUST_ENABLED is False`` AND no ``point_adjust``
                           function exists (PA can make random scores look SOTA).
  2. data leakage       -> ``detect_leaky_features`` catches a PLANTED leak (a column that
                           equals/encodes the label).
  3. temporal leakage   -> the split is PAST -> FUTURE (``is_temporal_split`` true,
                           ``assert_not_random_split`` passes; a shuffled split is rejected).
  4. synthetic-only     -> the synthetic-only guard is present and acknowledged.

Also checks entity-disjoint splitting (no entity in both train and test).

Pure pandas/numpy + ml.eval -> no heavy model, no torch.

Run: .mlvenv/bin/python -m pytest tests/ml/test_leakage.py -q
"""

from __future__ import annotations

import pytest

import ml.eval.metrics as _metrics
from ml.adapters import DataSimFeatureSource
from ml.eval import (
    POINT_ADJUST_ENABLED,
    assert_no_point_adjust,
    assert_not_random_split,
    detect_leaky_features,
    entity_disjoint_split,
    is_entity_disjoint,
    is_temporal_split,
    remove_leaky_features,
    synthetic_only_guard,
    temporal_split,
)


@pytest.fixture(scope="module")
def events():
    src = DataSimFeatureSource()
    ev = src.events().reset_index(drop=True)
    lab = (
        src.labels()
        .set_index("event_id")["is_fraud"]
        .reindex(ev["event_id"])
        .fillna(False)
    )
    ev = ev.assign(is_fraud=lab.astype(int).to_numpy())
    return ev


# --------------------------------------------------------------------------- #
# 1. point-adjust is disabled by construction                                  #
# --------------------------------------------------------------------------- #
def test_point_adjust_is_never_enabled():
    assert POINT_ADJUST_ENABLED is False
    # No point_adjust function may exist anywhere in the metrics module.
    assert not hasattr(
        _metrics, "point_adjust"
    ), "a point_adjust() function must not exist"
    assert_no_point_adjust()  # raises if PA ever gets re-enabled


# --------------------------------------------------------------------------- #
# 2. data-leakage detector catches a planted leak                              #
# --------------------------------------------------------------------------- #
def test_leakage_detector_catches_planted_leak(events):
    df = events.copy()
    # Plant a leak: a feature that IS the label (perfectly predictive).
    df["leaky_copy"] = df["is_fraud"].astype(float)
    # And a near-perfect encoded leak.
    df["leaky_noisy"] = df["is_fraud"].astype(float) * 100.0

    numeric = df[["leaky_copy", "leaky_noisy", "is_fraud"]]
    leaks = detect_leaky_features(numeric, "is_fraud")
    assert "leaky_copy" in leaks, "a column equal to the label must be flagged as leaky"
    assert "leaky_noisy" in leaks, "a perfectly-encoded label leak must be flagged"

    cleaned = remove_leaky_features(numeric, "is_fraud")
    assert "leaky_copy" not in cleaned.columns and "leaky_noisy" not in cleaned.columns
    assert "is_fraud" in cleaned.columns, "the label column itself must be kept"


def test_genuine_features_not_flagged_as_leaky(events):
    """A real, weakly-predictive feature must NOT be flagged (no false positives)."""
    src = DataSimFeatureSource()
    X, y = src.supervised_xy()
    df = X.assign(is_fraud=y.to_numpy())
    leaks = detect_leaky_features(df, "is_fraud")
    # The honest event features (amount, hour, ...) are NOT label copies.
    assert "amount" not in leaks and "hour" not in leaks and "is_off_hours" not in leaks


# --------------------------------------------------------------------------- #
# 3. temporal split is past -> future; a random split is rejected              #
# --------------------------------------------------------------------------- #
def test_temporal_split_is_past_to_future(events):
    train, test = temporal_split(events, "ts", test_frac=0.25)
    assert is_temporal_split(train, test, "ts"), "test must be strictly in the future"
    assert_not_random_split(train, test, "ts")  # must NOT raise


def test_random_split_is_rejected(events):
    shuffled = events.sample(frac=1.0, random_state=1405).reset_index(drop=True)
    n = len(shuffled)
    cut = int(n * 0.75)
    train, test = shuffled.iloc[:cut], shuffled.iloc[cut:]
    # A shuffled (random) split mixes the future into the past -> guard must reject it.
    with pytest.raises(AssertionError):
        assert_not_random_split(train, test, "ts")


# --------------------------------------------------------------------------- #
# entity-disjoint split holds                                                 #
# --------------------------------------------------------------------------- #
def test_entity_disjoint_split_holds(events):
    train, test = entity_disjoint_split(
        events, "actor.employee_id", test_frac=0.25, seed=1405
    )
    assert not train.empty and not test.empty
    assert is_entity_disjoint(
        train, test, "actor.employee_id"
    ), "no employee may appear in both train and test"


# --------------------------------------------------------------------------- #
# 4. synthetic-only guard present + acknowledged                               #
# --------------------------------------------------------------------------- #
def test_synthetic_only_guard_present():
    guard = synthetic_only_guard()
    d = guard.to_dict()
    assert d["synthetic_only"] is True
    assert d["acknowledged"] is True
    assert (
        "synthetic" in d["message"].lower()
    ), "the limitation must be documented in plain text"
