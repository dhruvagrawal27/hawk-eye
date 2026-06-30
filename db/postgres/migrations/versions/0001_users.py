"""users — RBAC subjects (DATABASE-2)

Blueprint Part 24.1 (8 RBAC roles) + Part 9.3 (app/metadata DB). DATABASE stores
the rows; BACKEND enforces the matrix (BACKEND.md §4). `keycloak_subject` ties a
row to the OIDC identity (PLATFORM/BACKEND own Keycloak).

Revision ID: 0001_users
Revises:
Create Date: 2026-06-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_users"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"
_ROLES = (
    "analyst",
    "senior_investigator",
    "team_lead",
    "compliance_officer",
    "auditor",
    "model_engineer",
    "platform_admin",
    "service_account",
)
_STATUS = ("active", "disabled", "suspended")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("keycloak_subject", sa.Text(), nullable=True, unique=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN (" + ", ".join(f"'{r}'" for r in _ROLES) + ")",
            name="ck_users_role",
        ),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in _STATUS) + ")",
            name="ck_users_status",
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_users_role", "users", ["role"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_users_role", table_name="users", schema=SCHEMA)
    op.drop_table("users", schema=SCHEMA)
