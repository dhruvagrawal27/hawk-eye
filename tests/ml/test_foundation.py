"""Foundation acceptance tests: ML-1 (scaffold/seeds/interfaces/adapters) + ML-2 (eval).

Blueprint refs: Part 8, Part 22.4 (seeds), Part 14, Part 20.0/20.4 (honest eval).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.base import Alert, ReasonCode, Severity, normalize_scores, severity_from_score
from ml.config import GLOBAL_SEED, seed_everything, seeded_rng
from ml import eval as E


# ----------------------------- ML-1 ----------------------------- #
def test_seed_is_reproducible():
    assert seed_everything() == GLOBAL_SEED
    a = seeded_rng().random(5)
    b = seeded_rng().random(5)
    assert np.allclose(a, b)


def test_reason_code_matches_backend_shape():
    assert ReasonCode("shap", feature="amount_z", contribution=0.31).to_dict() == {
        "source": "shap", "feature": "amount_z", "contribution": 0.31
    }
    assert ReasonCode("rule", code="NEW_BENE", detail="x").to_dict() == {
        "source": "rule", "code": "NEW_BENE", "detail": "x"
    }
    assert ReasonCode("graph", detail="ring RNG-12").to_dict() == {"source": "graph", "detail": "ring RNG-12"}


def test_alert_to_dict_matches_backend_keys():
    a = Alert("alr_1", "EMP-1", 87, "high", 0.82, contributing_layers=["L2", "L3"],
              reason_codes=[ReasonCode("rule", code="X", detail="y")], exposure_inr=4800000)
    d = a.to_dict()
    for key in ("alert_id", "entity_id", "risk_score", "severity", "confidence", "status",
                "created_ts", "contributing_layers", "reason_codes", "exposure_inr",
                "sla_due_ts", "pii_tokenized"):
        assert key in d
    assert d["risk_score"] == 87 and d["pii_tokenized"] is True


def test_severity_banding():
    assert severity_from_score(95) == Severity.CRITICAL
    assert severity_from_score(87) == Severity.HIGH
    assert severity_from_score(50) == Severity.MEDIUM
    assert severity_from_score(10) == Severity.LOW


def test_normalize_scores_rank_to_unit_interval():
    ns = normalize_scores(np.array([3.0, 1.0, 2.0]), "rank")
    assert ns.min() == 0.0 and ns.max() == 1.0 and int(np.argmax(ns)) == 0


def test_feature_source_separates_fraud(entity_xy):
    en, enl = entity_xy
    fraud = en.index[enl.reindex(en.index).fillna(0) == 1]
    norm = en.index[enl.reindex(en.index).fillna(0) == 0]
    if len(fraud) and len(norm):
        assert en.loc[fraud, "amount_max"].mean() >= en.loc[norm, "amount_max"].mean()


def test_synthetic_source_columns_match_l0(synthetic_source):
    ev = synthetic_source.events()
    for col in ("event_id", "ts", "actor.employee_id", "action.verb", "object.amount",
                "context.is_off_hours", "linkage.maker_id"):
        assert col in ev.columns


# ----------------------------- ML-2 ----------------------------- #
def test_real_signal_beats_random(supervised_xy):
    X, y = supervised_xy
    yv = y.to_numpy()
    real = (X["amount_z_personal"].to_numpy() + 0.5 * X["is_off_hours"].to_numpy()
            + X["verb_approve_payment"].to_numpy() * X["log1p_amount"].to_numpy() / 15)
    rand = np.random.default_rng(0).random(len(yv))
    assert E.average_precision(yv, real) > E.average_precision(yv, rand)


def test_comparison_table_always_has_random_baseline(supervised_xy):
    X, y = supervised_xy
    tbl = E.comparison_table(y.to_numpy(), {"real": X["amount_z_personal"].to_numpy()})
    assert any(r["name"] == "__random__" for r in tbl)


def test_temporal_split_is_past_to_future(data_source):
    ev = data_source.events()
    tr, te = E.temporal_split(ev, "ts", 0.25)
    assert E.is_temporal_split(tr, te, "ts")
    E.assert_not_random_split(tr, te, "ts")


def test_random_split_is_rejected(data_source):
    ev = data_source.events().sample(frac=1.0, random_state=0).reset_index(drop=True)
    half = len(ev) // 2
    import pytest

    with pytest.raises(AssertionError):
        E.assert_not_random_split(ev.iloc[:half], ev.iloc[half:], "ts")


def test_entity_disjoint_split(data_source):
    ev = data_source.events()
    tr, te = E.entity_disjoint_split(ev, "actor.employee_id", 0.25)
    assert E.is_entity_disjoint(tr, te, "actor.employee_id")


def test_leaky_feature_is_caught(supervised_xy):
    X, y = supervised_xy
    Xl = X.copy()
    Xl["LEAK"] = y.to_numpy().astype(float)
    Xl["is_fraud"] = y.to_numpy()
    leaky = E.detect_leaky_features(Xl, "is_fraud")
    assert "LEAK" in leaky
    assert len([c for c in leaky if c != "LEAK"]) <= 2  # no flood of false positives under imbalance


def test_point_adjust_is_impossible():
    E.assert_no_point_adjust()
    assert E.POINT_ADJUST_ENABLED is False


def test_vus_pr_and_range_metrics_run(supervised_xy):
    X, y = supervised_xy
    s = X["amount_z_personal"].to_numpy()
    assert 0.0 <= E.vus_pr(y.to_numpy(), s) <= 1.0
    pr = E.affiliation_pr(y.to_numpy(), s, threshold=float(np.quantile(s, 0.99)))
    assert set(pr) == {"range_precision", "range_recall", "range_f1"}
