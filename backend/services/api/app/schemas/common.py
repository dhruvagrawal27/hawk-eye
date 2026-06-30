"""Shared enums, ID helpers, and base types (BACKEND-4).

IDs follow CONTEXT.md §6 conventions: ``evt_*`` events, ``alr_*`` alerts, ``aud_*`` audit,
``RNG-*`` rings, entity_id = employee_id (``EMP-*``). Time is UTC ISO-8601 (``...Z``).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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


class DispositionOutcome(str, Enum):
    FRAUD = "fraud"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"


class Role(str, Enum):
    """8 roles — blueprint Part 24.1."""

    ANALYST = "analyst"
    SENIOR_INVESTIGATOR = "senior_investigator"
    TEAM_LEAD = "team_lead"  # Team Lead / MLRO
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR = "auditor"
    MODEL_ENGINEER = "model_engineer"  # Model Engineer / Data Scientist
    PLATFORM_ADMIN = "platform_admin"
    SERVICE_ACCOUNT = "service_account"


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
    return datetime.now(tz=timezone.utc)


def iso_z(dt: datetime) -> str:
    """ISO-8601 with a trailing ``Z`` (CONTEXT.md §6)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
