"""L0 Unified Event Model — canonical actor -> action -> object event (DATA-1).

Blueprint Part 5.1 (l.162-173) and Part 24.5(a). MUST stay field-compatible with
BACKEND.md §1 (DATA owns the schema, BACKEND consumes). Five field groups:
Actor / Action / Object / Context / Linkage.

Implemented with stdlib dataclasses (no pydantic dependency) so the package imports
and validates anywhere. `validate_event` returns a list of human-readable errors.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Actor:
    employee_id: str
    role: Optional[str] = None
    dept: Optional[str] = None
    branch: Optional[str] = None
    tenure_days: Optional[int] = None
    manager_id: Optional[str] = None
    peer_group: Optional[str] = None
    privileged_flag: bool = False
    leaver_flag: bool = False
    notice_period: bool = False


@dataclass
class Action:
    verb: str                              # login, create_beneficiary, approve_payment, db_select, export, grant_entitlement, ...
    channel: Optional[str] = None          # cbs, swift, rtgs, neft, imps, upi, db, dlp, hr, iam, pam
    maker_checker: Optional[str] = None    # "maker" | "checker" | None


@dataclass
class ObjectRef:
    account_id: Optional[str] = None
    beneficiary_id: Optional[str] = None
    table: Optional[str] = None            # table/dataset for data-layer events
    entitlement_id: Optional[str] = None
    instrument: Optional[str] = None       # SWIFT / LC / LoU
    amount: Optional[int] = None           # integer minor units where possible
    currency: Optional[str] = None


@dataclass
class Context:
    ts: Optional[str] = None               # mirrors top-level ts; UTC ISO-8601 "...Z"
    src_ip: Optional[str] = None
    device: Optional[str] = None
    geo: Optional[str] = None
    session_id: Optional[str] = None
    layer: Optional[str] = None            # "application" | "database"
    is_off_hours: Optional[bool] = None
    host: Optional[str] = None


@dataclass
class Linkage:
    """Correlation keys joining SWIFT<->CBS, app-txn<->DB-write, maker<->checker,
    employee<->customer-account (blueprint 5.1)."""
    swift_ref: Optional[str] = None
    cbs_ref: Optional[str] = None
    app_txn_id: Optional[str] = None
    db_write_id: Optional[str] = None
    maker_id: Optional[str] = None
    checker_id: Optional[str] = None
    customer_account: Optional[str] = None


@dataclass
class L0Event:
    event_id: str
    ts: str                                # UTC ISO-8601 "...Z"
    actor: Actor
    action: Action
    object: ObjectRef = field(default_factory=ObjectRef)
    context: Context = field(default_factory=Context)
    linkage: Linkage = field(default_factory=Linkage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "actor": asdict(self.actor),
            "action": asdict(self.action),
            "object": asdict(self.object),
            "context": asdict(self.context),
            "linkage": asdict(self.linkage),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "L0Event":
        return cls(
            event_id=d["event_id"],
            ts=d["ts"],
            actor=Actor(**d.get("actor", {})),
            action=Action(**d.get("action", {})),
            object=ObjectRef(**d.get("object", {})),
            context=Context(**d.get("context", {})),
            linkage=Linkage(**d.get("linkage", {})),
        )


# ---- Validation (no jsonschema dependency required) -------------------------
_REQUIRED_TOP = ("event_id", "ts")


def validate_event(d: dict[str, Any]) -> list[str]:
    """Return a list of validation errors; empty list == valid."""
    errors: list[str] = []
    for k in _REQUIRED_TOP:
        if not d.get(k):
            errors.append(f"missing required top-level field: {k}")
    actor = d.get("actor") or {}
    if not actor.get("employee_id"):
        errors.append("missing required actor.employee_id")
    action = d.get("action") or {}
    if not action.get("verb"):
        errors.append("missing required action.verb")
    ts = d.get("ts")
    if ts and not (isinstance(ts, str) and ts.endswith("Z")):
        errors.append("ts must be UTC ISO-8601 ending in 'Z'")
    for group in ("actor", "action", "object", "context", "linkage"):
        if group in d and not isinstance(d[group], dict):
            errors.append(f"field group '{group}' must be an object/dict")
    return errors


def is_valid(d: dict[str, Any]) -> bool:
    return not validate_event(d)


# ---- Avro schema (DATA-2 registry) ------------------------------------------
def _opt(name: str, avro_type: str = "string") -> dict:
    return {"name": name, "type": ["null", avro_type], "default": None}


AVRO_SCHEMA: dict[str, Any] = {
    "type": "record",
    "name": "L0Event",
    "namespace": "hawkeye.data",
    "fields": [
        {"name": "event_id", "type": "string"},
        {"name": "ts", "type": "string"},
        {"name": "actor", "type": {"type": "record", "name": "Actor", "fields": [
            {"name": "employee_id", "type": "string"},
            _opt("role"), _opt("dept"), _opt("branch"), _opt("tenure_days", "int"),
            _opt("manager_id"), _opt("peer_group"),
            {"name": "privileged_flag", "type": "boolean", "default": False},
            {"name": "leaver_flag", "type": "boolean", "default": False},
            {"name": "notice_period", "type": "boolean", "default": False},
        ]}},
        {"name": "action", "type": {"type": "record", "name": "Action", "fields": [
            {"name": "verb", "type": "string"}, _opt("channel"), _opt("maker_checker"),
        ]}},
        {"name": "object", "type": {"type": "record", "name": "ObjectRef", "fields": [
            _opt("account_id"), _opt("beneficiary_id"), _opt("table"),
            _opt("entitlement_id"), _opt("instrument"), _opt("amount", "long"), _opt("currency"),
        ]}},
        {"name": "context", "type": {"type": "record", "name": "Context", "fields": [
            _opt("ts"), _opt("src_ip"), _opt("device"), _opt("geo"), _opt("session_id"),
            _opt("layer"), _opt("is_off_hours", "boolean"), _opt("host"),
        ]}},
        {"name": "linkage", "type": {"type": "record", "name": "Linkage", "fields": [
            _opt("swift_ref"), _opt("cbs_ref"), _opt("app_txn_id"), _opt("db_write_id"),
            _opt("maker_id"), _opt("checker_id"), _opt("customer_account"),
        ]}},
    ],
}

# ---- JSON schema (lightweight; used by governance/contract tests) -----------
JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "L0Event",
    "type": "object",
    "required": ["event_id", "ts", "actor", "action"],
    "properties": {
        "event_id": {"type": "string", "pattern": "^evt_"},
        "ts": {"type": "string", "pattern": "Z$"},
        "actor": {"type": "object", "required": ["employee_id"]},
        "action": {"type": "object", "required": ["verb"]},
        "object": {"type": "object"},
        "context": {"type": "object"},
        "linkage": {"type": "object"},
    },
}

# ---- Canonical sample (matches BACKEND.md §1 / Part 24.5(a)) -----------------
SAMPLE_EVENT: dict[str, Any] = {
    "event_id": "evt_8f2a1c90",
    "ts": "2026-06-30T02:14:07Z",
    "actor": {"employee_id": "EMP-7f3a", "role": "ops_maker", "dept": "trade_finance",
              "branch": "BR-219", "tenure_days": 2840, "manager_id": "EMP-1a09",
              "peer_group": "PG-ops-tf", "privileged_flag": False, "leaver_flag": False,
              "notice_period": False},
    "action": {"verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker"},
    "object": {"beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "table": None,
               "entitlement_id": None, "instrument": None, "amount": None, "currency": "INR"},
    "context": {"ts": "2026-06-30T02:14:07Z", "src_ip": "10.20.4.31", "device": "WS-114",
                "geo": "Mumbai", "session_id": "sess_55e1", "layer": "application",
                "is_off_hours": True, "host": None},
    "linkage": {"swift_ref": None, "cbs_ref": None, "app_txn_id": None, "db_write_id": None,
                "maker_id": "EMP-7f3a", "checker_id": None, "customer_account": "ACCT-4d22"},
}
