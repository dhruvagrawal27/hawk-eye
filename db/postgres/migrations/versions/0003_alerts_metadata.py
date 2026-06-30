"""alerts_metadata — relational mirror of ClickHouse alerts (DATABASE-2)

Blueprint Part 11 + BACKEND.md §2. The *full* alert body lives in ClickHouse
(`hawkeye.alerts`); this is the lightweight relational mirror for case-workflow
joins (assignee, SLA, status transitions). Kept in sync by BACKEND on alert
create/transition.

Revision ID: 0003_alerts_metadata
Revises: 0002_cases
Create Date: 2026-06-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_alerts_metadata"
down_revision = "0002_cases"
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"
_SEVERITY = ("low", "medium", "high")
_STATUS = (
    "open",
    "assigned",
    "in_review",
    "block_requested",
    "confirmed_fraud",
    "false_positive",
    "inconclusive",
    "closed",
)


def upgrade() -> None:
    op.create_table(
        "alerts_metadata",
        sa.Column("alert_id", sa.Text(), primary_key=True),  # alr_*
        sa.Column("entity_id", sa.Text(), nullable=False),  # EMP-*
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.SmallInteger(), nullable=True),  # 0..100
        sa.Column("exposure_inr", sa.BigInteger(), nullable=True),
        sa.Column("sla_due_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "assignee",
            sa.Text(),
            sa.ForeignKey(f"{SCHEMA}.users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "severity IN (" + ", ".join(f"'{s}'" for s in _SEVERITY) + ")",
            name="ck_alerts_severity",
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _STATUS) + ")",
            name="ck_alerts_status",
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_alerts_risk_range",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_alerts_entity", "alerts_metadata", ["entity_id"], schema=SCHEMA)
    op.create_index("ix_alerts_status", "alerts_metadata", ["status"], schema=SCHEMA)
    op.create_index(
        "ix_alerts_assignee", "alerts_metadata", ["assignee"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_assignee", table_name="alerts_metadata", schema=SCHEMA)
    op.drop_index("ix_alerts_status", table_name="alerts_metadata", schema=SCHEMA)
    op.drop_index("ix_alerts_entity", table_name="alerts_metadata", schema=SCHEMA)
    op.drop_table("alerts_metadata", schema=SCHEMA)
