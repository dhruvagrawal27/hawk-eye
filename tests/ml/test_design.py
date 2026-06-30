"""ML-9 design tests: peer-relative scoring + alert-only contract + decision summary."""

from __future__ import annotations

import os

import pandas as pd
import pytest

from ml.design import (
    Advisory,
    AlertOnlyViolation,
    alert_only_contract,
    assert_advisory_action,
    peer_group_from_features,
    peer_relative_scores,
)


def test_peer_relative_scoring_normalises_within_group():
    # Two peer groups with different absolute levels; a within-group outlier must surface.
    scores = pd.Series(
        [10, 11, 12, 50, 100, 101, 102, 140],
        index=[f"E{i}" for i in range(8)],
        dtype=float,
    )
    groups = pd.Series(["A"] * 4 + ["B"] * 4, index=scores.index)
    z = peer_relative_scores(scores, groups)
    # The within-group high outlier (E3=50 in A, E7=140 in B) should score highest per group.
    assert z["E3"] == z.iloc[:4].max()
    assert z["E7"] == z.iloc[4:].max()
    # Absolute level does not dominate: B's lowest (100) is not flagged above A's outlier.
    assert z["E4"] < z["E3"]


def test_peer_group_from_features_uses_data_peer_group():
    ef = pd.DataFrame(index=pd.Index(["EMP-1", "EMP-2"], name="employee_id"))
    ev = pd.DataFrame(
        {
            "actor.employee_id": ["EMP-1", "EMP-2"],
            "actor.peer_group": ["PG-ops", "PG-treasury"],
        }
    )
    pg = peer_group_from_features(ef, ev)
    assert pg.loc["EMP-1"] == "PG-ops" and pg.loc["EMP-2"] == "PG-treasury"


def test_alert_only_contract_blocks_autonomous_actions():
    assert_advisory_action("alert")  # ok
    assert_advisory_action("escalate_for_review")  # ok
    for bad in ("block", "freeze", "auto_classify_fraud", "reverse_transaction"):
        with pytest.raises(AlertOnlyViolation):
            assert_advisory_action(bad)


def test_advisory_cannot_be_constructed_with_blocking_action():
    Advisory(entity_id="EMP-1", risk_score=87.0, action="alert")  # ok
    with pytest.raises(AlertOnlyViolation):
        Advisory(entity_id="EMP-1", risk_score=87.0, action="block")


def test_alert_only_contract_is_published():
    c = alert_only_contract()
    assert c["no_inline_blocking"] is True
    assert "block" in c["forbidden_autonomous_actions"]
    assert "alert" in c["allowed_advisory_actions"]


def test_decision_summary_exists_with_layer_table():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "ml",
        "design",
        "decision_summary.md",
    )
    with open(path) as fh:
        text = fh.read()
    for layer in ("L1", "L2", "L3", "L4", "L5", "L6"):
        assert layer in text
    assert "Isolation Forest" in text and "LightGBM" in text and "XGB-Graph" in text
