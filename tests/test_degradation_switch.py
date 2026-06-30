"""Unit tests for the degradation switch (PLATFORM-4/28, Part 18 / Part 30.1).

Proves: (1) the canonical fraud burst alerts in both modes; (2) ALERT-ONLY — every
alert is human-pending (status=open), never an action; (3) rules-only marks events for
re-score so nothing is dropped; (4) benign activity is suppressed.
"""
import pytest
from dswitch import rules, scoring

FRAUD = {
    "event_id": "evt_t1", "ts": "2026-06-30T02:14:07Z",
    "actor": {"employee_id": "EMP-7f3a", "tenure_days": 2840, "leaver_flag": False},
    "action": {"verb": "approve_payment", "channel": "cbs", "maker_checker": "checker"},
    "object": {"beneficiary_id": "BEN-9b1c", "amount": 4_800_000, "currency": "INR",
               "new_beneficiary": True, "beneficiary_age_min": 27},
    "context": {"is_off_hours": True, "layer": "application"},
    "linkage": {"maker_employee_id": "EMP-1a09", "maker_checker_isolated_pair": True},
}
BENIGN = {
    "event_id": "evt_t2", "ts": "2026-06-30T11:00:00Z",
    "actor": {"employee_id": "EMP-aaaa", "tenure_days": 1000},
    "action": {"verb": "view_balance", "channel": "cbs"},
    "object": {"amount": 0}, "context": {"is_off_hours": False, "layer": "application"},
}


def test_rules_fire_on_known_typologies():
    codes = {rc["code"] for rc in rules.evaluate(FRAUD)}
    assert "NEW_BENEFICIARY_THEN_HIGHVALUE" in codes
    assert "OFF_HOURS_HIGH_VALUE" in codes
    assert "MAKER_CHECKER_COLLUSION_HINT" in codes


def test_swift_cbs_mismatch_rule():
    ev = {"action": {"channel": "swift"}, "linkage": {"cbs_entry_present": False}, "object": {}}
    codes = {rc["code"] for rc in rules.evaluate(ev)}
    assert "SWIFT_CBS_MISMATCH" in codes


def test_db_write_no_app_txn_rule():
    ev = {"context": {"layer": "database"}, "linkage": {"app_txn_present": False},
          "action": {}, "object": {}}
    assert any(rc["code"] == "DB_WRITE_NO_APP_TXN" for rc in rules.evaluate(ev))


def test_full_mode_fuses_layers():
    a = scoring.score_event(FRAUD, "full", {"L2_unsupervised": 0.82, "L3_gbdt": 0.78, "L5_graph": 0.7})
    assert a is not None
    assert "L1_rules" in a["contributing_layers"]
    assert "L3_gbdt" in a["contributing_layers"]
    assert a["scoring_mode"] == "full"


def test_rules_only_alerts_and_marks_rescore():
    a = scoring.score_event(FRAUD, "rules_only")
    assert a is not None
    assert a["scoring_mode"] == "rules_only"
    assert a["marked_for_rescore"] is True
    assert a["contributing_layers"] == ["L1_rules"]


def test_alert_only_invariant():
    """GOLDEN RULE 1: every alert is human-pending; the scorer never returns an action."""
    for mode in ("full", "rules_only"):
        a = scoring.score_event(FRAUD, mode, {"L3_gbdt": 0.9})
        assert a["status"] == "open"
        assert "action" not in a and "auto_block" not in a


def test_benign_suppressed_both_modes():
    assert scoring.score_event(BENIGN, "rules_only") is None
    assert scoring.score_event(BENIGN, "full", {"L2_unsupervised": 0.05, "L3_gbdt": 0.05}) is None


def test_malformed_event_never_crashes():
    # a rule subset must tolerate garbage (Part 32.2 resilience)
    assert rules.evaluate({}) == []
    assert scoring.score_event({"event_id": "x"}, "rules_only") is None


def test_alert_shape_matches_backend_contract():
    a = scoring.score_event(FRAUD, "rules_only")
    for k in ("alert_id", "entity_id", "risk_score", "severity", "confidence",
              "status", "contributing_layers", "reason_codes", "exposure_inr", "pii_tokenized"):
        assert k in a, f"missing BACKEND.md §2 field: {k}"
    assert a["alert_id"].startswith("alr_")
    assert a["pii_tokenized"] is True
