"""Shared enums, ID helpers, and base types (BACKEND-4).

IDs follow CONTEXT.md §6 conventions: ``evt_*`` events, ``alr_*`` alerts, ``aud_*`` audit,
``RNG-*`` rings, entity_id = employee_id (``EMP-*``). Time is UTC ISO-8601 (``...Z``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum


# --- Enums (mirror blueprint Part 24.1 / 24.5) ---
class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AlertStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_REVIEW = "in_review"
    BLOCK_REQUESTED = "block_requested"
    CONFIRMED_FRAUD = "confirmed_fraud"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"
    CLOSED = "closed"


class ContributingLayer(str, Enum):
    L1_RULES = "L1_rules"
    L2_UNSUPERVISED = "L2_unsupervised"
    L3_GBDT = "L3_gbdt"
    L4_SEQUENCE = "L4_sequence"
    L5_GRAPH = "L5_graph"


class ReasonSource(str, Enum):
    RULE = "rule"
    SHAP = "shap"
    GRAPH = "graph"
    SEQUENCE = "sequence"
    # ML emits "attention" for L4 sequence-attention (LAXCAT) evidence; "sequence" and
    # "attention" are synonyms. Accept both so reason codes from ML are never rejected at the
    # seam (cross-workstream contract reconciliation — see CONTEXT.md). red-team: contract_conformance
    ATTENTION = "attention"


class DispositionOutcome(str, Enum):
    FRAUD = "fraud"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"


class Role(str, Enum):
    """12 console/RBAC roles — bank org chart, FROZEN spec (docs/BANK_ROLES.md).

    PSB (Union Bank-style) org chart mapped onto RBI's Three Lines of Defense. 11 human +
    1 service. Capability semantics and the 9 capabilities are unchanged from Part 24.1; only
    the role identities and hierarchy are new. Order: top-of-chart first.

    These are the *console/RBAC* roles (who uses the fraud console). Do not confuse with the
    *actor/subject* roles in ``data/sim/*`` (ops_maker, ops_checker, …) — those are the
    monitored employees inside events and are a separate, unchanged axis.
    """

    MANAGING_DIRECTOR = "managing_director"  # Managing Director & CEO (Board)
    EXECUTIVE_DIRECTOR = "executive_director"  # Executive Director (Board)
    CGM_RISK = "cgm_risk"  # CGM — Chief Risk Officer (Executive)
    DGM_COMPLIANCE = "dgm_compliance"  # DGM — Risk & Compliance
    AGM_VIGILANCE = "agm_vigilance"  # AGM — Vigilance & Fraud Risk (fraud-function lead / MLRO)
    CHIEF_INTERNAL_AUDITOR = "chief_internal_auditor"  # Chief Internal Auditor (3rd line)
    DATA_SCIENCE_LEAD = "data_science_lead"  # Head — Data Science / Model Risk
    CLUSTER_HEAD = "cluster_head"  # Cluster Head / Zonal Manager
    BRANCH_MANAGER = "branch_manager"  # Branch Manager
    RELATIONSHIP_MANAGER = "relationship_manager"  # Relationship Manager (branch ops)
    IT_ADMIN = "it_admin"  # IT / Platform Administrator
    SERVICE_ACCOUNT = "service_account"  # Service Account (system)


class Capability(str, Enum):
    """9 capabilities — blueprint Part 24.1 (column order preserved)."""

    VIEW_ALERTS = "view_alerts"
    TRIAGE_ASSIGN = "triage_assign"
    DISPOSITION = "disposition"
    REQUEST_BLOCK = "request_block"
    UNMASK_PII = "unmask_pii"
    TUNE_RULES = "tune_rules"
    TRAIN_DEPLOY_MODELS = "train_deploy_models"
    VIEW_AUDIT = "view_audit"
    ADMIN = "admin"


# --- Time / ID helpers ---
def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def iso_z(dt: datetime) -> str:
    """ISO-8601 with a trailing ``Z`` (CONTEXT.md §6)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _rand(n: int) -> str:
    return uuid.uuid4().hex[:n]


def new_event_id() -> str:
    return f"evt_{_rand(8)}"


def new_alert_id() -> str:
    return f"alr_{_rand(6)}"


def new_audit_id() -> str:
    return f"aud_{_rand(6)}"


def new_ring_id() -> str:
    return f"RNG-{_rand(4)}"


def new_case_id() -> str:
    return f"case_{_rand(6)}"
