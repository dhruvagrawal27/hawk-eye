"""Escalation/SLA + L6 fusion calibration unit tests (BACKEND-23/12)."""

from __future__ import annotations

from app.workflow.escalation import internal_tat_days, route_for_severity, sla_due_ts
from fusion.calibration import calibrate_probability, confidence_from, severity_for
from fusion.service import DEFAULT_FUSION


def test_sla_due_is_rbi_30_day_cap():
    # created + 30 days (RBI ≤30-day). Matches the Part 24.5b example deadline.
    assert sla_due_ts("2026-06-30T02:41:55Z") == "2026-07-30T02:41:55Z"


def test_internal_tat_tighter_for_high():
    assert internal_tat_days("high") == 7
    assert internal_tat_days("medium") == 15
    assert internal_tat_days("low") == 30
    assert internal_tat_days("high") <= 30  # never exceeds RBI cap


def test_routing_by_severity():
    assert route_for_severity("high").value == "senior_investigator"
    assert route_for_severity("low").value == "analyst"


def test_calibration_bounds():
    assert calibrate_probability(0.0) == 0
    assert calibrate_probability(1.0) == 100
    assert calibrate_probability(0.5) == 50
    assert severity_for(85) == "high"
    assert severity_for(50) == "medium"
    assert severity_for(10) == "low"
    assert severity_for(10, hard_hit=True) == "high"
    assert 0.0 <= confidence_from([0.8, 0.82, 0.9], 0.87) <= 1.0


def test_fusion_hard_hit_is_high():
    out = DEFAULT_FUSION.fuse(
        scores={"L2_unsupervised": 0.77, "L3_gbdt": 0.79},
        model_versions={"L2_unsupervised": "v", "L3_gbdt": "v"},
        features={"is_off_hours": True, "minutes_since_new_beneficiary": 19},
        l1_score=0.9,
        l1_hard_hit=True,
        l1_reason_codes=[{"source": "rule", "code": "NEW_BENEFICIARY_THEN_HIGHVALUE", "detail": "x"}],
        graph_evidence=["maker EMP-7f3a + checker EMP-1a09 isolated pair (ring RNG-12)"],
    )
    assert out.severity == "high"
    assert 0 <= out.risk_score <= 100 and out.risk_score >= 70
    assert "L1_rules" in out.contributing_layers and "L5_graph" in out.contributing_layers
    sources = {rc["source"] for rc in out.reason_codes}
    assert {"rule", "shap", "graph"} <= sources  # rule provenance + SHAP + graph evidence
    assert out.model_versions.get("L6_fusion")  # L6 meta version recorded


def test_fusion_calibrated_0_100_and_confidence():
    out = DEFAULT_FUSION.fuse(
        scores={"L2_unsupervised": 0.2, "L3_gbdt": 0.1},
        features={},
        l1_score=0.0,
    )
    assert 0 <= out.risk_score <= 100
    assert 0.0 <= out.confidence <= 1.0
