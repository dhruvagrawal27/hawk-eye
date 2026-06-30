"""FMR generator (BACKEND-24, blueprint Part 16).

FMR = Fraud Monitoring Returns. Generates FMR line items from confirmed-fraud cases (synthetic).
SCAFFOLD: real generator logic; live RBI FMR submission channel absent. Alert-only / natural
justice: an FMR line is produced only AFTER a human disposition of ``fraud`` — never auto-classified.
"""

from __future__ import annotations

# Coarse synthetic mapping of typology → RBI FMR fraud category.
_CATEGORY = {
    "NEW_BENEFICIARY_THEN_HIGHVALUE": "misappropriation_breach_of_trust",
    "DB_WRITE_WITHOUT_APP_TXN": "manipulation_of_books",
    "ENTITLEMENT_SELF_GRANT": "unauthorised_credit_facility",
    "SWIFT_CBS_MISMATCH": "cheating_forgery",
    "DORMANT_REACTIVATION_DRAIN": "misappropriation_breach_of_trust",
}


def fmr_category(reason_codes: list[dict]) -> str:
    for rc in reason_codes:
        code = rc.get("code")
        if code in _CATEGORY:
            return _CATEGORY[code]
    return "others"


def fmr_line(case: dict) -> dict:
    """Build one FMR line from a confirmed-fraud case dict."""
    return {
        "fmr_id": f"fmr_{case['alert_id'].replace('alr_', '')}",
        "entity_id": case["entity_id"],
        "alert_id": case["alert_id"],
        "category": fmr_category(case.get("reason_codes", [])),
        "amount_inr": int(case.get("exposure_inr", 0)),
        "detected_ts": case.get("created_ts", ""),
        "rfa_tagged": bool(case.get("rfa_tagged", False)),
        "status": "reported",
    }


def generate(
    confirmed_fraud_cases: list[dict], *, period: str = "current", submission_enabled: bool = False
) -> dict:
    items = [fmr_line(c) for c in confirmed_fraud_cases]
    return {
        "period": period,
        "submission_enabled": submission_enabled,
        "items": items,
        "total_amount_inr": sum(i["amount_inr"] for i in items),
    }
