"""Case-scoped access (BACKEND-22, blueprint Part 19.3/24.1).

Need-to-know enforcement: an Analyst sees ONLY their assigned cases; a Model Engineer sees
de-identified data only; Senior+ see all. Used to filter alert queues and to gate single-alert
reads. Every view is separately audited ("watch the watchers") by the route layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from app.auth.principal import Principal
from app.schemas.common import Role

T = TypeVar("T")


def sees_all_cases(principal: Principal) -> bool:
    """Roles that are not restricted to assigned cases."""
    return principal.role in (
        Role.SENIOR_INVESTIGATOR,
        Role.TEAM_LEAD,
        Role.COMPLIANCE_OFFICER,
        Role.AUDITOR,  # read-only, all
    )


def can_view_alert(principal: Principal, alert_id: str, assignee: str | None) -> bool:
    """Whether this principal may view this specific alert."""
    if sees_all_cases(principal):
        return True
    if principal.role == Role.ANALYST:
        # Assigned-only: the alert must be in the analyst's case scope or assigned to them.
        return alert_id in principal.assigned_alerts or assignee == principal.user_id
    # Model Engineer: de-identified view permitted (route de-identifies the payload).
    return principal.role == Role.MODEL_ENGINEER


def filter_visible(principal: Principal, alerts: Iterable[T], *, id_of, assignee_of) -> list[T]:
    """Filter an iterable of alerts down to those the principal may see."""
    if sees_all_cases(principal) or principal.role == Role.MODEL_ENGINEER:
        return list(alerts)
    if principal.role == Role.ANALYST:
        return [
            a
            for a in alerts
            if id_of(a) in principal.assigned_alerts or assignee_of(a) == principal.user_id
        ]
    return []
