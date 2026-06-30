"""Audit + admin contracts (BACKEND-22, blueprint Part 24.2/19.3/29.2).

Every action — including investigators' (who-viewed-whom, "watch the watchers") — is an
immutable audit event written to DATABASE's WORM store.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Role


class AuditEvent(BaseModel):
    # WORM tamper-evidence (Part 19.3): the model is FROZEN (written once, never mutated in
    # place) and carries a hash-chain (``prev_hash`` -> ``entry_hash``) so any post-write edit
    # to who-viewed-whom is *detectable* via ``AuditWriter.verify_chain()``, even on the
    # in-memory shim. ``immutable=True`` is therefore enforced, not decorative.
    model_config = ConfigDict(frozen=True)

    audit_id: str
    ts: str
    actor: str = Field(..., description="Who performed the action (tokenized user id)")
    actor_role: Role | str
    action: str = Field(
        ..., description="e.g. alert.view, alert.disposition, pii.unmask, rule.change"
    )
    target: str | None = Field(None, description="Subject of the action (e.g. entity / alert id)")
    detail: dict = Field(default_factory=dict)
    immutable: bool = True
    prev_hash: str = Field("GENESIS", description="entry_hash of the previous audit event (chain link)")
    entry_hash: str = Field("", description="sha256(prev_hash + canonical content) — tamper-evidence")


class AuditPage(BaseModel):
    items: list[AuditEvent]
    total: int
    limit: int
    offset: int


class UserRecord(BaseModel):
    user_id: str
    display_name: str
    role: Role
    active: bool = True
    sod_constraints: list[str] = Field(
        default_factory=list, description="e.g. cannot_label_data, cannot_close_own_alerts"
    )


class CreateUserRequest(BaseModel):
    user_id: str
    display_name: str
    role: Role


class UserList(BaseModel):
    items: list[UserRecord]
