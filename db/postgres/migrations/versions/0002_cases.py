"""cases + case_notes + case_history — investigation case workflow (DATABASE-2)

Blueprint Part 11 (investigation workflow) + Part 24.5 (case management). FRONTEND
screen 4 + BACKEND `/cases` bind here. `linked_alert_ids` joins to the ClickHouse
`alerts` body (full alert lives in ClickHouse; metadata mirrored in alerts_metadata).

Revision ID: 0002_cases
Revises: 0001_users
Create Date: 2026-06-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_cases"
down_revision = "0001_users"
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"
_CASE_STATUS = ("open", "in_progress", "escalated", "closed")


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("case_id", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column(
            "assignee",
            sa.Text(),
            sa.ForeignKey(f"{SCHEMA}.users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "linked_alert_ids",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("notes_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _CASE_STATUS) + ")",
            name="ck_cases_status",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_cases_status", "cases", ["status"], schema=SCHEMA)
    op.create_index("ix_cases_assignee", "cases", ["assignee"], schema=SCHEMA)

    op.create_table(
        "case_notes",
        sa.Column("note_id", sa.Text(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Text(),
            sa.ForeignKey(f"{SCHEMA}.cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_case_notes_case", "case_notes", ["case_id"], schema=SCHEMA)

    op.create_table(
        "case_history",
        sa.Column("history_id", sa.Text(), primary_key=True),
        sa.Column(
            "case_id",
            sa.Text(),
            sa.ForeignKey(f"{SCHEMA}.cases.case_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=True),
        sa.Column("audit_id", sa.Text(), nullable=True),  # ties to WORM (DATABASE-6)
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_case_history_case", "case_history", ["case_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_case_history_case", table_name="case_history", schema=SCHEMA)
    op.drop_table("case_history", schema=SCHEMA)
    op.drop_index("ix_case_notes_case", table_name="case_notes", schema=SCHEMA)
    op.drop_table("case_notes", schema=SCHEMA)
    op.drop_index("ix_cases_assignee", table_name="cases", schema=SCHEMA)
    op.drop_index("ix_cases_status", table_name="cases", schema=SCHEMA)
    op.drop_table("cases", schema=SCHEMA)
