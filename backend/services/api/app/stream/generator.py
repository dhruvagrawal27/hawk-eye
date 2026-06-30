"""Synthetic L0 event generator + tick builder for the live stream.

Produces L0 events in the shape ``OnlinePipeline.process`` expects, front-loading high-risk
("mule burst") events so real alerts fire within seconds. The ``event.scored`` tick matches the
frontend RealtimeTick contract; ``alert`` JSON matches the frontend Alert type.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

_ROLES = ["ops_maker", "ops_checker", "trade_finance", "teller", "admin_dba", "relationship_mgr"]
_VERBS = ["approve_payment", "create_beneficiary", "db_select", "export", "grant_entitlement", "login"]
_CHANNELS = ["cbs", "swift", "internet", "db", "admin_console"]

_seq = 100000


def _next() -> int:
    global _seq
    _seq += 1
    return _seq


def make_event(hot: bool) -> dict[str, Any]:
    """One synthetic L0 event. ``hot`` makes it off-hours + just-under-threshold + privileged."""
    sid = _next()
    emp = f"EMP-{random.randint(0x7000, 0x7FFF):x}"
    off_hours = random.random() < (0.7 if hot else 0.18)
    # hot = Rs 45–49L (structuring just under the 50L reporting line); else routine amounts
    amount = (random.randint(45, 49) * 100000 + random.randint(0, 999) * 10) if hot else random.randint(1, 30) * 10000
    return {
        "event_id": f"evt_{sid}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": {
            "employee_id": emp,
            "role": random.choice(_ROLES),
            "dept": "trade_finance",
            "branch": f"BR-{random.randint(100, 399)}",
            "privileged_flag": hot or random.random() < 0.3,
            "tenure_days": random.randint(200, 4000),
        },
        "action": {
            "verb": "approve_payment" if hot else random.choice(_VERBS),
            "channel": random.choice(_CHANNELS),
            "maker_checker": random.choice(["maker", "checker"]),
        },
        "object": {
            "beneficiary_id": f"BEN-{random.randint(1000, 9999)}",
            "account_id": f"ACCT-{random.randint(1, 99)}",
            "amount": amount,
            "currency": "INR",
        },
        "context": {
            "is_off_hours": off_hours,
            "src_ip": f"10.{random.randint(0, 40)}.{random.randint(0, 255)}.{random.randint(1, 254)}",
            "device": f"WS-{random.randint(100, 140)}",
            "geo": "Mumbai",
            "session_id": f"sess_{sid}",
            "layer": "application",
        },
        "linkage": {"maker_id": f"EMP-{random.randint(0x7000, 0x7FFF):x}", "checker_id": emp},
    }


def _risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def make_tick(event: dict[str, Any], alert: Any | None) -> dict[str, Any]:
    """Build the event.scored tick. Real score when an alert fired; an honest sub-threshold
    estimate for events scored below the alert line."""
    actor = event.get("actor", {})
    obj = event.get("object", {})
    ctx = event.get("context", {})
    if alert is not None:
        score = int(alert.risk_score)
        is_alert = True
        rc = alert.reason_codes[0] if getattr(alert, "reason_codes", None) else None
        top = getattr(rc, "code", None) or getattr(rc, "detail", None) if rc else None
    else:
        base = 8 + (24 if ctx.get("is_off_hours") else 0) + min(24, int(obj.get("amount", 0)) // 250000)
        score = min(66, base + random.randint(0, 8))
        is_alert = False
        top = None
    verb = event.get("action", {}).get("verb", "")
    return {
        "type": "event.scored",
        "tick_id": _next(),
        "employee_id": actor.get("employee_id", "EMP-?"),
        "account_id": obj.get("account_id", ""),
        "score": score,
        "risk_level": _risk_level(score),
        "is_alert": is_alert,
        "top_signal": top,
        "amount": int(obj.get("amount", 0)),
        "txn_type": "debit" if "payment" in verb else ("config" if "grant" in verb else "access"),
        "channel": event.get("action", {}).get("channel", "cbs"),
        "is_after_hours": bool(ctx.get("is_off_hours")),
        "ts": event.get("ts", datetime.now(timezone.utc).isoformat()),
    }


def alert_json(alert: Any) -> dict[str, Any]:
    """Serialize a backend Alert to the frontend Alert JSON shape."""
    return alert.model_dump(mode="json")
