"""Append-only audit writer (BACKEND-22, blueprint Part 19.3 / 29.2).

Every action — alert views (who-viewed-whom), assignments, dispositions, unmasks, rule changes,
model promotions, admin changes, narrative generations — writes an immutable audit event. This is
"watch the watchers": investigators' actions are audited and subject to fairness review.

# STUB: DATABASE (WORM / object-lock immutable store). Append-only in-memory shim: events are
never mutated or deleted; ``query`` is read-only. Swap for DATABASE's WORM store with no call-site
change.
"""

from __future__ import annotations

import hashlib
import json

from app.observability.metrics import UNMASK_EVENTS
from app.schemas.audit import AuditEvent
from app.schemas.common import Role, iso_z, new_audit_id, utcnow

GENESIS = "GENESIS"


def _content_digest(
    *, audit_id: str, ts: str, actor: str, actor_role: str, action: str,
    target: str | None, detail: dict, prev_hash: str,
) -> str:
    """sha256 over the canonical entry content chained to the previous entry's hash."""
    payload = json.dumps(
        {"audit_id": audit_id, "ts": ts, "actor": actor, "actor_role": actor_role,
         "action": action, "target": target, "detail": detail},
        sort_keys=True, default=str, separators=(",", ":"),
    )
    return hashlib.sha256((prev_hash + "\n" + payload).encode()).hexdigest()


class AuditWriter:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []  # append-only

    def write(
        self,
        *,
        actor: str,
        actor_role: Role | str,
        action: str,
        target: str | None = None,
        detail: dict | None = None,
    ) -> AuditEvent:
        role_str = actor_role.value if isinstance(actor_role, Role) else str(actor_role)
        audit_id = new_audit_id()
        ts = iso_z(utcnow())
        det = detail or {}
        prev_hash = self._events[-1].entry_hash if self._events else GENESIS
        entry_hash = _content_digest(
            audit_id=audit_id, ts=ts, actor=actor, actor_role=role_str,
            action=action, target=target, detail=det, prev_hash=prev_hash,
        )
        event = AuditEvent(
            audit_id=audit_id,
            ts=ts,
            actor=actor,
            actor_role=role_str,
            action=action,
            target=target,
            detail=det,
            immutable=True,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._events.append(event)
        if action == "pii.unmask":
            UNMASK_EVENTS.inc(role=event.actor_role)
        return event

    def verify_chain(self) -> bool:
        """Recompute the hash-chain; returns False if ANY entry was tampered (WORM check)."""
        prev = GENESIS
        for e in self._events:
            expected = _content_digest(
                audit_id=e.audit_id, ts=e.ts, actor=e.actor, actor_role=str(e.actor_role),
                action=e.action, target=e.target, detail=e.detail, prev_hash=prev,
            )
            if e.entry_hash != expected or e.prev_hash != prev:
                return False
            prev = e.entry_hash
        return True

    def query(
        self,
        *,
        actor: str | None = None,
        target: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        items = self._events
        if actor:
            items = [e for e in items if e.actor == actor]
        if target:
            items = [e for e in items if e.target == target]
        if action:
            items = [e for e in items if e.action == action]
        items = list(reversed(items))  # newest first
        total = len(items)
        return items[offset : offset + limit], total

    def all(self) -> list[AuditEvent]:
        return list(self._events)


AUDIT = AuditWriter()
