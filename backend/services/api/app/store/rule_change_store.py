"""Four-eyes rule-change proposals (BACKEND-8).

# STUB: DATABASE (Postgres rules/approvals). A rule change is a *proposal* until a second approver
(≠ proposer) signs off; only then does the engine apply + persist the new version. Holds the
pending proposals between propose and approve.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class ChangeProposal:
    change_id: str
    code: str
    proposed_by: str
    diff: dict
    change_reason: str
    status: str = "pending_approval"  # pending_approval | approved | rejected
    approver: str | None = None
    new_version: str | None = None
    overlap_alerts: set[str] = field(default_factory=set)


class RuleChangeStore:
    def __init__(self) -> None:
        self._proposals: dict[str, ChangeProposal] = {}

    def create(self, code: str, proposed_by: str, diff: dict, reason: str) -> ChangeProposal:
        change_id = f"chg_{uuid.uuid4().hex[:6]}"
        proposal = ChangeProposal(
            change_id=change_id,
            code=code,
            proposed_by=proposed_by,
            diff=diff,
            change_reason=reason,
        )
        self._proposals[change_id] = proposal
        return proposal

    def get(self, change_id: str) -> ChangeProposal | None:
        return self._proposals.get(change_id)

    def list(self) -> list[ChangeProposal]:
        return list(self._proposals.values())

    def resolve(self, change_id: str, approver: str, approved: bool, new_version: str | None) -> ChangeProposal | None:
        proposal = self._proposals.get(change_id)
        if proposal:
            proposal.status = "approved" if approved else "rejected"
            proposal.approver = approver
            proposal.new_version = new_version if approved else None
        return proposal


RULE_CHANGES = RuleChangeStore()
