"""Pydantic request/response contracts (BACKEND-4). Mirror of BACKEND.md §1–§7."""

from app.schemas.alerts import Alert, AlertPage, ReasonCode
from app.schemas.audit import AuditEvent, AuditPage, CreateUserRequest, UserList, UserRecord
from app.schemas.common import (
    AlertStatus,
    Capability,
    ContributingLayer,
    DispositionOutcome,
    ReasonSource,
    Role,
    Severity,
)
from app.schemas.disposition import (
    AssignRequest,
    BlockRequest,
    BlockRequestResponse,
    DispositionRequest,
    DispositionResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from app.schemas.entities import (
    EntityGraph,
    EntityProfile,
    EntityTimeline,
    PeerComparison,
    UnmaskRequest,
    UnmaskResponse,
)
from app.schemas.events import L0Event
from app.schemas.explanations import Explanation
from app.schemas.models import DriftReport, ModelInfo, ModelQuality, PromoteRequest, PromoteResult
from app.schemas.narratives import NarrativeAuditMemo, NarrativeResponse
from app.schemas.reports import CrilcReport, FmrReport
from app.schemas.rules import (
    RuleApproval,
    RuleApprovalResult,
    RuleChangeProposal,
    RuleChangeRequest,
    RuleSummary,
)

__all__ = [
    "Alert",
    "AlertPage",
    "ReasonCode",
    "AuditEvent",
    "AuditPage",
    "CreateUserRequest",
    "UserList",
    "UserRecord",
    "AlertStatus",
    "Capability",
    "ContributingLayer",
    "DispositionOutcome",
    "ReasonSource",
    "Role",
    "Severity",
    "AssignRequest",
    "BlockRequest",
    "BlockRequestResponse",
    "DispositionRequest",
    "DispositionResponse",
    "FeedbackRequest",
    "FeedbackResponse",
    "EntityGraph",
    "EntityProfile",
    "EntityTimeline",
    "PeerComparison",
    "UnmaskRequest",
    "UnmaskResponse",
    "L0Event",
    "Explanation",
    "DriftReport",
    "ModelInfo",
    "ModelQuality",
    "PromoteRequest",
    "PromoteResult",
    "NarrativeAuditMemo",
    "NarrativeResponse",
    "CrilcReport",
    "FmrReport",
    "RuleApproval",
    "RuleApprovalResult",
    "RuleChangeProposal",
    "RuleChangeRequest",
    "RuleSummary",
]
