"""Case-scoped access (BACKEND-22, blueprint Part 19.3/24.1, FROZEN roles docs/BANK_ROLES.md).

Need-to-know enforcement: a Relationship Manager sees ONLY their assigned cases; the de-identified
roles (Data Science, CGM/ED/MD exec & board) see de-identified aggregates only; Branch Manager and
up the 1st/3rd-line chain see all case data. Used to filter alert queues and to gate single-alert
reads. Every view is separately audited ("watch the watchers") by the route layer.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from app.auth.principal import Principal
from app.schemas.common import Role

T = TypeVar("T")

# Roles that see only de-identified aggregates (no case PII): Data Science + exec/board.
# Mirrors the ``de_identified_only`` view grants in docs/BANK_ROLES.md (view = C("de_identified_only")).
_DEIDENTIFIED_ROLES = {
    Role.DATA_SCIENCE_LEAD,
    Role.CGM_RISK,
    Role.EXECUTIVE_DIRECTOR,
    Role.MANAGING_DIRECTOR,
}


def sees_all_cases(principal: Principal) -> bool:
    """Roles that see full case data and are not restricted to assigned cases."""
    return principal.role in (
        Role.BRANCH_MANAGER,
        Role.CLUSTER_HEAD,
        Role.AGM_VIGILANCE,
        Role.DGM_COMPLIANCE,
        Role.CHIEF_INTERNAL_AUDITOR,  # read-only, all
    )


def can_view_alert(principal: Principal, alert_id: str, assignee: str | None) -> bool:
    """Whether this principal may view this specific alert."""
    if sees_all_cases(principal):
        return True
    if principal.role == Role.RELATIONSHIP_MANAGER:
        # Assigned-only: the alert must be in the RM's case scope or assigned to them.
        return alert_id in principal.assigned_alerts or assignee == principal.user_id
    # De-identified roles: de-identified view permitted (route de-identifies the payload).
    return principal.role in _DEIDENTIFIED_ROLES


def filter_visible(principal: Principal, alerts: Iterable[T], *, id_of, assignee_of) -> list[T]:
    """Filter an iterable of alerts down to those the principal may see."""
    if sees_all_cases(principal) or principal.role in _DEIDENTIFIED_ROLES:
        return list(alerts)
    if principal.role == Role.RELATIONSHIP_MANAGER:
        return [
            a
            for a in alerts
            if id_of(a) in principal.assigned_alerts or assignee_of(a) == principal.user_id
        ]
    return []
