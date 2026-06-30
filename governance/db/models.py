"""SQLAlchemy models for the governance DB (PLATFORM-32).

Mirror governance/db/schema.sql exactly, but use portable types so the governance-api,
seed, and go-live tooling run on **SQLite** (local/CI, zero infra) AND **Postgres**
(compose/prod). Pick the backend with GOVERNANCE_DB_URL
(default: sqlite:///<repo>/governance/db/governance.db).
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

_DEFAULT = f"sqlite:///{Path(__file__).resolve().parent / 'governance.db'}"
DB_URL = os.environ.get("GOVERNANCE_DB_URL", _DEFAULT)


class Base(DeclarativeBase):
    pass


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    policy_type: Mapped[str] = mapped_column(String(40))
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approval_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    resolution_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    doc_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class Committee(Base):
    __tablename__ = "committees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    committee_type: Mapped[str] = mapped_column(String(40))
    charter: Mapped[str | None] = mapped_column(Text, nullable=True)
    cadence: Mapped[str | None] = mapped_column(String(60), nullable=True)


class CommitteeMember(Base):
    __tablename__ = "committee_members"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"))
    member_name: Mapped[str] = mapped_column(String(200))
    member_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    org_function: Mapped[str | None] = mapped_column(String(40), nullable=True)


class CommitteeMinutes(Base):
    __tablename__ = "committee_minutes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committees.id"))
    meeting_date: Mapped[dt.date] = mapped_column(Date)
    agenda: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisions: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    attendees: Mapped[str | None] = mapped_column(Text, nullable=True)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_type: Mapped[str] = mapped_column(String(40))
    artifact_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    decision: Mapped[str] = mapped_column(String(20), default="pending")
    approver: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approver_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    approval_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    resolution_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelValidation(Base):
    __tablename__ = "model_validations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(60))
    risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    conceptual_soundness: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    performance: Mapped[str | None] = mapped_column(Text, nullable=True)
    stability: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_grounding: Mapped[str | None] = mapped_column(Text, nullable=True)
    validator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signoff_status: Mapped[str] = mapped_column(String(20), default="pending")
    signoff_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    vendor_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    due_diligence: Mapped[str | None] = mapped_column(Text, nullable=True)
    sla: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    concentration_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_clauses: Mapped[str | None] = mapped_column(Text, nullable=True)
    sbom_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="assessed")


class DPIA(Base):
    __tablename__ = "dpia"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    lawful_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_rating: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dpo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approval_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    audit_report: Mapped[str | None] = mapped_column(Text, nullable=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reported_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_deadline: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    opened_ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    closed_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class SecurityReport(Base):
    __tablename__ = "security_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    signoff: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    report_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(300), nullable=True)


class UATSignoff(Base):
    __tablename__ = "uat_signoffs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario: Mapped[str] = mapped_column(String(200))
    cases_total: Mapped[int] = mapped_column(Integer, default=0)
    cases_passed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    signoff: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signoff_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(300), nullable=True)


class OperatingMetric(Base):
    __tablename__ = "operating_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(60))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    period: Mapped[str | None] = mapped_column(String(40), nullable=True)
    computed_ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class StaffingPlan(Base):
    __tablename__ = "staffing_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario: Mapped[str] = mapped_column(String(100))
    alert_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    handling_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sla_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    roster: Mapped[str | None] = mapped_column(Text, nullable=True)


class GoLiveTick(Base):
    __tablename__ = "go_live_ticks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(40))
    item: Mapped[str] = mapped_column(String(300))
    evidence_table: Mapped[str | None] = mapped_column(String(60), nullable=True)
    evidence_filter: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="not_met")
    evidence_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    updated_ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class GovernanceAudit(Base):
    __tablename__ = "governance_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


# Map evidence-table names (used by go_live_ticks.evidence_table) to model classes.
TABLE_MODELS = {
    "policies": Policy, "committees": Committee, "committee_minutes": CommitteeMinutes,
    "approvals": Approval, "model_validations": ModelValidation, "vendors": Vendor,
    "dpia": DPIA, "incidents": Incident, "security_reports": SecurityReport,
    "uat_signoffs": UATSignoff, "operating_metrics": OperatingMetric,
    "staffing_plans": StaffingPlan,
}


def get_engine(url: str | None = None):
    return create_engine(url or DB_URL, future=True)


def get_session(url: str | None = None):
    engine = get_engine(url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def init_db(url: str | None = None) -> None:
    Base.metadata.create_all(get_engine(url))
