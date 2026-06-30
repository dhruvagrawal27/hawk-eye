"""Severity-based escalation routing + SLA/TAT timers (BACKEND-23, blueprint Part 33.3 / 11).

Populates ``sla_due_ts`` on every alert. The RBI cap is **≤30 days**; higher severity gets a
tighter internal TAT (capped at the RBI limit). Routing maps severity → the queue/role that owns it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config import settings
from app.schemas.alerts import Alert
from app.schemas.common import Role

# Internal TAT per severity (days) — used to PRIORITIZE the queue, never exceeding the RBI cap.
_INTERNAL_TAT_DAYS = {"high": 7, "medium": 15, "low": 30}

# Severity → owning role/queue (FROZEN roles docs/BANK_ROLES.md: high escalates to the Branch
# Manager; medium/low sit with the Relationship Manager in the branch triage queue).
_ROUTING = {
    "high": Role.BRANCH_MANAGER,
    "medium": Role.RELATIONSHIP_MANAGER,
    "low": Role.RELATIONSHIP_MANAGER,
}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def sla_due_ts(created_ts: str, severity: str | None = None, *, max_days: int | None = None) -> str:
    """Regulatory SLA deadline = created + RBI cap (≤30 days). This is the value on the alert."""
    days = max_days if max_days is not None else settings.sla_days_default
    return _iso_z(_parse(created_ts) + timedelta(days=days))


def internal_tat_days(severity: str) -> int:
    """Tighter internal turnaround target per severity (for prioritization/escalation, ≤ RBI cap)."""
    return min(
        _INTERNAL_TAT_DAYS.get(severity, settings.sla_days_default), settings.sla_days_default
    )


def route_for_severity(severity: str) -> Role:
    return _ROUTING.get(severity, Role.RELATIONSHIP_MANAGER)


def apply_sla(alert: Alert) -> Alert:
    """Populate ``sla_due_ts`` (RBI ≤30-day deadline) on an alert (idempotent)."""
    alert.sla_due_ts = sla_due_ts(alert.created_ts)
    return alert
