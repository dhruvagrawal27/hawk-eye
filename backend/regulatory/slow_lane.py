"""Slow-lane entity/credit scoring (BACKEND-25, blueprint Part 12 / 13 / 18.2).

Daily/weekly batch scoring for red-flagged accounts feeding the EWS/CRILC pipeline. This is NOT a
generic scorer — it scores the **four named Part-12 typologies**, consuming the DATA slow-lane
features (DATA-20/21) and the ``lane:slow`` simulator traces (DATA-9), and emits RFA tags + EWS
indicators. SCAFFOLD only because the live RBI submission channel is absent; the typology scoring
runs REAL on synthetic data.

Typologies:
  (a) fake-vendor / billing
  (b) ghost-employees / payroll
  (c) alert-suppression by AML watchers
  (d) ghost / insider-loans + inflated-appraisal
"""

from __future__ import annotations

from regulatory.ews import EWS_INDICATORS

RFA_SCORE_THRESHOLD = 0.5


def _weighted(rec: dict, weights: dict[str, float]) -> tuple[float, list[str]]:
    """Score = Σ(weight · indicator-present) normalised by Σweights; returns (score, fired indicators)."""
    fired = [k for k in weights if rec.get(k)]
    num = sum(weights[k] for k in fired)
    den = sum(weights.values()) or 1.0
    return round(num / den, 3), fired


def score_fake_vendor(rec: dict) -> dict:
    score, fired = _weighted(
        rec,
        {
            "vendor_address_equals_employee_address": 0.4,
            "single_client_vendor": 0.25,
            "round_invoice_amounts": 0.15,
            "sequential_invoice_numbers": 0.2,
        },
    )
    return _result("fake_vendor", score, fired)


def score_ghost_employee(rec: dict) -> dict:
    score, fired = _weighted(
        rec,
        {
            "no_tax_footprint": 0.4,
            "duplicated_bank_details": 0.35,
            "no_attendance_record": 0.15,
            "salary_to_shared_account": 0.1,
        },
    )
    return _result("ghost_employee", score, fired)


def score_alert_suppression(rec: dict) -> dict:
    score, fired = _weighted(
        rec,
        {
            "disproportionate_clear_rate": 0.45,
            "reopened_then_cleared": 0.3,
            "cleared_without_edd": 0.25,
        },
    )
    return _result("alert_suppression", score, fired)


def score_ghost_loan(rec: dict) -> dict:
    score, fired = _weighted(
        rec,
        {
            "thin_documentation": 0.3,
            "appraiser_is_borrower": 0.35,
            "disbursement_to_non_sanctioned_account": 0.25,
            "inflated_appraisal_ratio": 0.1,
        },
    )
    return _result("ghost_loan", score, fired)


_SCORERS = {
    "fake_vendor": score_fake_vendor,
    "ghost_employee": score_ghost_employee,
    "alert_suppression": score_alert_suppression,
    "ghost_loan": score_ghost_loan,
}


def _result(typology: str, score: float, indicators: list[str]) -> dict:
    return {
        "typology": typology,
        "score": score,
        "indicators": indicators,
        "rfa_tagged": score >= RFA_SCORE_THRESHOLD,
        "ews_indicators": [EWS_INDICATORS[typology]] if score >= RFA_SCORE_THRESHOLD else [],
    }


def score_record(rec: dict) -> list[dict]:
    """Score a slow-lane record against ALL four typologies (a record may match more than one)."""
    typ = rec.get("typology")
    scorers = {typ: _SCORERS[typ]} if typ in _SCORERS else _SCORERS
    return [scorer(rec) for scorer in scorers.values()]


def score_batch(records: list[dict]) -> list[dict]:
    """Score a batch and return only the typology hits at/above the RFA threshold."""
    out: list[dict] = []
    for rec in records:
        for res in score_record(rec):
            if res["rfa_tagged"]:
                out.append({"entity_id": rec.get("entity_id"), **res})
    return out
