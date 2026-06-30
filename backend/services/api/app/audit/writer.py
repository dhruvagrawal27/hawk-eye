"""Append-only audit writer (BACKEND-22, blueprint Part 19.3 / 29.2).

Every action — alert views (who-viewed-whom), assignments, dispositions, unmasks, rule changes,
model promotions, admin changes, narrative generations — writes an immutable audit event. This is
"watch the watchers": investigators' actions are audited and subject to fairness review.

# STUB: DATABASE (WORM / object-lock immutable store). Append-only in-memory shim: events are
never mutated or deleted; ``query`` is read-only. Swap for DATABASE's WORM store with no call-site
change.
"""

from __future__ import annotations

from app.observability.metrics import UNMASK_EVENTS
from app.schemas.audit import AuditEvent
from app.schemas.common import Role, iso_z, new_audit_id, utcnow


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
        event = AuditEvent(
            audit_id=new_audit_id(),
            ts=iso_z(utcnow()),
            actor=actor,
            actor_role=actor_role.value if isinstance(actor_role, Role) else str(actor_role),
            action=action,
            target=target,
            detail=detail or {},
            immutable=True,
        )
        self._events.append(event)
        if action == "pii.unmask":
            UNMASK_EVENTS.inc(role=event.actor_role)
        return event

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
