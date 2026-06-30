"""L0 unified event (BACKEND consumes; DATA owns the schema — BACKEND.md §1, blueprint 5.1/24.5a).

BACKEND does **not** define this shape — it is replicated here only so the rules engine and the
online path can validate/parse the canonical actor/action/object/context/linkage event. If a field
is needed that DATA does not emit, propose it in CONTEXT.md and tag DATA (do not change it here).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Actor(BaseModel):
    model_config = ConfigDict(extra="allow")
    employee_id: str = Field(..., examples=["EMP-7f3a"])
    role: str | None = None
    dept: str | None = None
    branch: str | None = None
    tenure_days: int | None = None
    peer_group: str | None = None
    privileged_flag: bool = False
    leaver_flag: bool = False


class Action(BaseModel):
    model_config = ConfigDict(extra="allow")
    verb: str = Field(..., examples=["create_beneficiary", "approve_payment"])
    channel: str | None = Field(None, examples=["cbs", "swift", "rtgs", "db", "iam"])
    maker_checker: str | None = Field(None, examples=["maker", "checker", None])


class Obj(BaseModel):
    model_config = ConfigDict(extra="allow")
    beneficiary_id: str | None = None
    account_id: str | None = None
    amount: int | None = Field(None, description="Integer minor units / INR (CONTEXT.md §6)")
    currency: str = "INR"


class Context(BaseModel):
    model_config = ConfigDict(extra="allow")
    src_ip: str | None = None
    device: str | None = None
    geo: str | None = None
    session_id: str | None = None
    layer: str | None = Field(None, examples=["application", "database", "network"])
    is_off_hours: bool = False


class Linkage(BaseModel):
    """Correlation keys joining SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer."""

    model_config = ConfigDict(extra="allow")
    swift_ref: str | None = None
    cbs_txn_id: str | None = None
    app_txn_id: str | None = None
    db_write_id: str | None = None
    related_event_id: str | None = None
    customer_account_id: str | None = None


class L0Event(BaseModel):
    """Canonical unified event (Part 24.5a). ``extra='allow'`` so DATA can evolve fields additively."""

    model_config = ConfigDict(extra="allow")
    event_id: str = Field(..., examples=["evt_8f2a1c90"])
    ts: str = Field(..., description="UTC ISO-8601 (…Z)", examples=["2026-06-30T02:14:07Z"])
    actor: Actor
    action: Action
    object: Obj = Field(default_factory=Obj)
    context: Context = Field(default_factory=Context)
    linkage: Linkage = Field(default_factory=Linkage)

    @staticmethod
    def example() -> dict:
        return {
            "event_id": "evt_8f2a1c90",
            "ts": "2026-06-30T02:14:07Z",
            "actor": {
                "employee_id": "EMP-7f3a",
                "role": "ops_maker",
                "dept": "trade_finance",
                "branch": "BR-219",
                "tenure_days": 2840,
                "peer_group": "PG-ops-tf",
                "privileged_flag": False,
                "leaver_flag": False,
            },
            "action": {"verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker"},
            "object": {
                "beneficiary_id": "BEN-9b1c",
                "account_id": "ACCT-4d22",
                "amount": None,
                "currency": "INR",
            },
            "context": {
                "src_ip": "10.20.4.31",
                "device": "WS-114",
                "geo": "Mumbai",
                "session_id": "sess_55e1",
                "layer": "application",
                "is_off_hours": True,
            },
        }
