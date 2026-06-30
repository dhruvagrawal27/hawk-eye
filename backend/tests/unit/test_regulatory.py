"""Regulatory generators unit tests (BACKEND-24/25): CRILC windows, slow-lane typologies, RFA."""

from __future__ import annotations

from regulatory import crilc, ews, fmr, rfa, slow_lane
from regulatory.util import THREE_CRORE_INR


def test_crilc_3cr_7day_180day_window():
    exposures = [
        {"entity_id": "EMP-4d99", "exposure_inr": 35_000_000, "detected_ts": "2026-06-28T11:20:00Z"},
        {"entity_id": "EMP-2b14", "exposure_inr": 2_000_000, "detected_ts": "2026-06-28T11:20:00Z"},
    ]
    report = crilc.generate(exposures)
    assert len(report["items"]) == 1  # only the ≥ ₹3-crore exposure is CRILC-reportable
    item = report["items"][0]
    assert item["crosses_3cr"] and item["exposure_inr"] >= THREE_CRORE_INR
    assert item["reporting_due_ts"] == "2026-07-05T11:20:00Z"  # +7 days
    assert item["classification_due_ts"] == "2026-12-25T11:20:00Z"  # +180 days


def test_three_crore_constant():
    assert THREE_CRORE_INR == 30_000_000


def test_fmr_category_mapping():
    case = {"alert_id": "alr_1", "entity_id": "EMP-7f3a", "exposure_inr": 4_800_000,
            "created_ts": "2026-06-30T02:41:55Z",
            "reason_codes": [{"code": "NEW_BENEFICIARY_THEN_HIGHVALUE"}]}
    report = fmr.generate([case])
    assert report["items"][0]["category"] == "misappropriation_breach_of_trust"


def test_rfa_tagging():
    tagged = rfa.tag({"reason_codes": [{"code": "SWIFT_CBS_MISMATCH"}], "exposure_inr": 0, "risk_score": 0})
    assert tagged["rfa_tagged"] is True


def test_slow_lane_all_four_typologies_scored():
    records = [
        {"entity_id": "V1", "typology": "fake_vendor", "vendor_address_equals_employee_address": True,
         "single_client_vendor": True, "round_invoice_amounts": True},
        {"entity_id": "E1", "typology": "ghost_employee", "no_tax_footprint": True,
         "duplicated_bank_details": True},
        {"entity_id": "A1", "typology": "alert_suppression", "disproportionate_clear_rate": True,
         "reopened_then_cleared": True},
        {"entity_id": "L1", "typology": "ghost_loan", "thin_documentation": True,
         "appraiser_is_borrower": True, "disbursement_to_non_sanctioned_account": True},
    ]
    hits = slow_lane.score_batch(records)
    typologies = {h["typology"] for h in hits}
    assert typologies == {"fake_vendor", "ghost_employee", "alert_suppression", "ghost_loan"}
    assert all(h["rfa_tagged"] for h in hits)
    assert all(h["ews_indicators"] for h in hits)


def test_ews_indicator_coverage():
    cov = ews.coverage({"NEW_BENEFICIARY_THEN_HIGHVALUE", "OFF_HOURS_ACTIVITY"})
    assert "EWS-funds-routed-to-new-beneficiary" in cov["covered"]
    assert 0.0 < cov["coverage_ratio"] <= 1.0
