"""model_governance + approvals — four-eyes model sign-off (DATABASE-2)

Blueprint Part 23.2 (per-version governance metadata) + Part 19.6 / BACKEND.md §4
(SoD: promoter != approver, second-person sign-off). DATABASE STORES the rows;
ML/BACKEND WRITE them (governance evidence seam — we don't author model cards).
Lineage URIs point at registry artifacts (DATABASE-7/8).

Revision ID: 0004_model_governance
Revises: 0003_alerts_metadata
Create Date: 2026-06-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_model_governance"
down_revision = "0003_alerts_metadata"
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"
_RISK_TIER = ("low", "medium", "high", "critical")
_DECISION = ("approve", "reject")


def upgrade() -> None:
    op.create_table(
        "model_governance",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("model", sa.Text(), nullable=False),  # e.g. lightgbm_gbdt
        sa.Column("version", sa.Text(), nullable=False),  # e.g. v1.4.2
        sa.Column("layer", sa.Text(), nullable=True),  # L2..L6
        sa.Column("owner", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("risk_tier", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("model_card_uri", sa.Text(), nullable=True),  # registry artifact
        sa.Column("validation_report_uri", sa.Text(), nullable=True),
        sa.Column("dataset_hash", sa.Text(), nullable=True),  # lineage (Part 21.5)
        sa.Column("feature_set_version", sa.Text(), nullable=True),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("model", "version", name="uq_model_version"),
        sa.CheckConstraint(
            "risk_tier IN (" + ", ".join(f"'{r}'" for r in _RISK_TIER) + ")",
            name="ck_model_risk_tier",
        ),
        schema=SCHEMA,
    )

    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.Text(), primary_key=True),
        sa.Column("model_version", sa.Text(), nullable=False),  # "model:version"
        sa.Column("approver", sa.Text(), nullable=False),
        sa.Column(
            "requested_by", sa.Text(), nullable=True
        ),  # SoD: requester != approver
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("audit_id", sa.Text(), nullable=True),  # WORM linkage (DATABASE-6)
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "decision IN (" + ", ".join(f"'{d}'" for d in _DECISION) + ")",
            name="ck_approvals_decision",
        ),
        # SoD invariant (Part 19.6): the approver cannot be the requester.
        sa.CheckConstraint(
            "requested_by IS NULL OR requested_by <> approver",
            name="ck_approvals_four_eyes",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_approvals_model_version", "approvals", ["model_version"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_approvals_model_version", table_name="approvals", schema=SCHEMA)
    op.drop_table("approvals", schema=SCHEMA)
    op.drop_table("model_governance", schema=SCHEMA)
