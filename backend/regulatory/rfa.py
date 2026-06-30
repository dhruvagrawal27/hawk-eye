"""RFA tagging (BACKEND-24, blueprint Part 16).

RFA = Red-Flagged Account. An account is tagged RFA when one or more early-warning signals are
present (an RFA is a presumption of fraud risk that triggers EDD — not a fraud classification).
"""

from __future__ import annotations

# Rule codes that, when present, warrant an RFA tag (EWS → RFA).
_RFA_TRIGGER_CODES = {
    "NEW_BENEFICIARY_THEN_HIGHVALUE",
    "DORMANT_REACTIVATION_DRAIN",
    "SWIFT_CBS_MISMATCH",
    "DB_WRITE_WITHOUT_APP_TXN",
    "ENTITLEMENT_SELF_GRANT",
}

RFA_EXPOSURE_INR = 50_00_000  # ₹50 lakh — escalate to RFA on material exposure


def should_tag_rfa(reason_codes: list[dict], exposure_inr: int = 0, risk_score: int = 0) -> bool:
    if exposure_inr >= RFA_EXPOSURE_INR and risk_score >= 70:
        return True
    return any(rc.get("code") in _RFA_TRIGGER_CODES for rc in reason_codes)


def tag(case: dict) -> dict:
    """Return the case annotated with ``rfa_tagged`` + the triggering signals."""
    codes = case.get("reason_codes", [])
    triggers = [rc.get("code") for rc in codes if rc.get("code") in _RFA_TRIGGER_CODES]
    rfa = should_tag_rfa(codes, int(case.get("exposure_inr", 0)), int(case.get("risk_score", 0)))
    return {**case, "rfa_tagged": rfa, "rfa_triggers": triggers}
