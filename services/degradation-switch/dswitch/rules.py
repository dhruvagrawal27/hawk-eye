"""L1 rules subset — the graceful-degradation continuity fallback (PLATFORM-4/28).

BACKEND owns the full rules/BRE + SoD/toxic-combination matrix (BACKEND-*, Part 11).
This is a SMALL, deliberately-labelled subset of the top Part 12/13 typologies that
the platform falls back to when ML serving is unhealthy, so the pipeline keeps
producing *rules-only* alerts (Part 18 continuity, Part 30.1 BCP graceful degradation).
It is NOT the production rules engine; the degradation switch containerizes/deploys
BACKEND's engine in prod and only uses this when BACKEND's L1 is also unreachable.

Each rule takes an L0 event (BACKEND.md §1) and returns a reason_code dict or None.
"""
from __future__ import annotations

from typing import Callable, Optional

ReasonCode = dict
Rule = Callable[[dict], Optional[ReasonCode]]

# Rule severities feed the rules-only risk score (0-100). Tuned so the canonical
# synthetic burst (create_beneficiary -> high-value approve, off-hours) alerts.
_SEV = {
    "NEW_BENEFICIARY_THEN_HIGHVALUE": 70,
    "SWIFT_CBS_MISMATCH": 80,
    "DB_WRITE_NO_APP_TXN": 75,
    "DORMANT_REACTIVATION": 55,
    "ENTITLEMENT_SELF_GRANT": 65,
    "OFF_HOURS_HIGH_VALUE": 45,
    "MAKER_CHECKER_COLLUSION_HINT": 50,
    "BULK_EXPORT_LEAVER_WINDOW": 60,
}

HIGH_VALUE_INR = 1_000_000  # ₹10 lakh threshold for "high value" (dev default)


def _amount(ev: dict) -> int:
    obj = ev.get("object") or {}
    return int(obj.get("amount") or 0)


def r_new_beneficiary_highvalue(ev: dict) -> Optional[ReasonCode]:
    act = (ev.get("action") or {}).get("verb", "")
    amt = _amount(ev)
    obj = ev.get("object") or {}
    # An approve/payment to a freshly-created/new beneficiary at high value.
    if act in ("approve_payment", "release_payment", "make_payment") and amt >= HIGH_VALUE_INR:
        if obj.get("beneficiary_id") and (obj.get("new_beneficiary") or obj.get("beneficiary_age_min", 999) < 60):
            return {
                "source": "rule", "code": "NEW_BENEFICIARY_THEN_HIGHVALUE",
                "detail": f"payment of INR {amt:,} to new payee {obj.get('beneficiary_id')} shortly after onboarding",
                "severity": _SEV["NEW_BENEFICIARY_THEN_HIGHVALUE"],
            }
    if act == "create_beneficiary" and (ev.get("context") or {}).get("is_off_hours"):
        return {
            "source": "rule", "code": "NEW_BENEFICIARY_THEN_HIGHVALUE",
            "detail": f"off-hours new-beneficiary creation {obj.get('beneficiary_id')} (watch for follow-on payment)",
            "severity": _SEV["NEW_BENEFICIARY_THEN_HIGHVALUE"] - 15,
        }
    return None


def r_swift_cbs_mismatch(ev: dict) -> Optional[ReasonCode]:
    lk = ev.get("linkage") or {}
    if (ev.get("action") or {}).get("channel") == "swift" and lk.get("cbs_entry_present") is False:
        return {
            "source": "rule", "code": "SWIFT_CBS_MISMATCH",
            "detail": "SWIFT instrument with no matching CBS posting (PNB/LoU-style reconciliation gap)",
            "severity": _SEV["SWIFT_CBS_MISMATCH"],
        }
    return None


def r_db_write_no_app_txn(ev: dict) -> Optional[ReasonCode]:
    ctx = ev.get("context") or {}
    lk = ev.get("linkage") or {}
    if ctx.get("layer") == "database" and lk.get("app_txn_present") is False:
        return {
            "source": "rule", "code": "DB_WRITE_NO_APP_TXN",
            "detail": "direct DB write with no corresponding application transaction (privileged manipulation)",
            "severity": _SEV["DB_WRITE_NO_APP_TXN"],
        }
    return None


def r_dormant_reactivation(ev: dict) -> Optional[ReasonCode]:
    obj = ev.get("object") or {}
    if (ev.get("action") or {}).get("verb") == "reactivate_account" and obj.get("dormant_days", 0) > 180:
        return {
            "source": "rule", "code": "DORMANT_REACTIVATION",
            "detail": f"dormant account reactivated after {obj.get('dormant_days')}d then immediate activity",
            "severity": _SEV["DORMANT_REACTIVATION"],
        }
    return None


def r_entitlement_self_grant(ev: dict) -> Optional[ReasonCode]:
    act = (ev.get("action") or {}).get("verb", "")
    actor = ev.get("actor") or {}
    obj = ev.get("object") or {}
    if act in ("grant_entitlement", "add_role") and obj.get("target_employee_id") == actor.get("employee_id"):
        return {
            "source": "rule", "code": "ENTITLEMENT_SELF_GRANT",
            "detail": "actor granted themselves an entitlement (short-lived admin / self-grant)",
            "severity": _SEV["ENTITLEMENT_SELF_GRANT"],
        }
    return None


def r_off_hours_high_value(ev: dict) -> Optional[ReasonCode]:
    ctx = ev.get("context") or {}
    if ctx.get("is_off_hours") and _amount(ev) >= HIGH_VALUE_INR:
        return {
            "source": "rule", "code": "OFF_HOURS_HIGH_VALUE",
            "detail": f"high-value (INR {_amount(ev):,}) action outside the actor's normal hours",
            "severity": _SEV["OFF_HOURS_HIGH_VALUE"],
        }
    return None


def r_maker_checker_hint(ev: dict) -> Optional[ReasonCode]:
    act = ev.get("action") or {}
    lk = ev.get("linkage") or {}
    if act.get("maker_checker") == "checker" and lk.get("maker_employee_id") and \
            lk.get("maker_checker_isolated_pair"):
        return {
            "source": "rule", "code": "MAKER_CHECKER_COLLUSION_HINT",
            "detail": f"maker {lk.get('maker_employee_id')} + checker recur as an isolated pair",
            "severity": _SEV["MAKER_CHECKER_COLLUSION_HINT"],
        }
    return None


def r_bulk_export_leaver(ev: dict) -> Optional[ReasonCode]:
    actor = ev.get("actor") or {}
    obj = ev.get("object") or {}
    if (ev.get("action") or {}).get("verb") == "export_data" and actor.get("leaver_flag") \
            and obj.get("record_count", 0) > 1000:
        return {
            "source": "rule", "code": "BULK_EXPORT_LEAVER_WINDOW",
            "detail": f"{obj.get('record_count')} records exported by a flagged leaver",
            "severity": _SEV["BULK_EXPORT_LEAVER_WINDOW"],
        }
    return None


RULES: list[Rule] = [
    r_new_beneficiary_highvalue,
    r_swift_cbs_mismatch,
    r_db_write_no_app_txn,
    r_dormant_reactivation,
    r_entitlement_self_grant,
    r_off_hours_high_value,
    r_maker_checker_hint,
    r_bulk_export_leaver,
]


def evaluate(ev: dict) -> list[ReasonCode]:
    """Return every fired rule's reason code for the event."""
    hits = []
    for rule in RULES:
        try:
            rc = rule(ev)
        except Exception:  # a malformed event must never crash the fallback
            rc = None
        if rc:
            hits.append(rc)
    return hits
