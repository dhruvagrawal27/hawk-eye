"""least-privilege roles + grants (DATABASE-2)

Blueprint Part 9.3 (least-privilege service accounts) + Part 28.2 (classification
drives access). Three NOLOGIN group roles the app's login users inherit:
  * hawkeye_migrate — DDL (owns migrations; never the app runtime role)
  * hawkeye_app     — DML on app tables (BACKEND runtime)
  * hawkeye_ro      — SELECT only (auditor / read paths)
The app NEVER runs as superuser. `pii_vault` is need-to-know: hawkeye_app only;
hawkeye_ro is explicitly REVOKED (unmask is a separate audited capability).

NOTE: creating roles requires a role-admin/superuser connection (the dev
POSTGRES_USER is the DB owner, which suffices). Reversible.

Revision ID: 0006_roles_grants
Revises: 0005_pii_vault
Create Date: 2026-06-30

"""

from __future__ import annotations

from alembic import op

revision = "0006_roles_grants"
down_revision = "0005_pii_vault"
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"
_ROLES = ("hawkeye_migrate", "hawkeye_app", "hawkeye_ro")


def upgrade() -> None:
    # ---- create the group roles idempotently --------------------------------
    for role in _ROLES:
        op.execute(
            f"DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN "
            f"CREATE ROLE {role} NOLOGIN; END IF; END $$;"
        )

    # ---- schema usage -------------------------------------------------------
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO hawkeye_app, hawkeye_ro")
    op.execute(f"GRANT USAGE, CREATE ON SCHEMA {SCHEMA} TO hawkeye_migrate")

    # ---- DDL role: everything (it authored the tables) ----------------------
    op.execute(f"GRANT ALL ON ALL TABLES IN SCHEMA {SCHEMA} TO hawkeye_migrate")
    op.execute(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {SCHEMA} TO hawkeye_migrate")

    # ---- app role: DML on app tables + sequence usage -----------------------
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {SCHEMA} "
        "TO hawkeye_app"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {SCHEMA} TO hawkeye_app"
    )

    # ---- read-only role: SELECT on everything... ----------------------------
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO hawkeye_ro")

    # ---- ...EXCEPT the PII vault (need-to-know; unmask is separate+audited) --
    op.execute(f"REVOKE ALL ON {SCHEMA}.pii_vault FROM hawkeye_ro")
    op.execute(f"REVOKE ALL ON {SCHEMA}.pii_vault FROM PUBLIC")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {SCHEMA}.pii_vault TO hawkeye_app")

    # ---- default privileges for FUTURE tables (created by hawkeye_migrate) ---
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hawkeye_app"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} "
        "GRANT SELECT ON TABLES TO hawkeye_ro"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} "
        "REVOKE SELECT ON TABLES FROM hawkeye_ro"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {SCHEMA} "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM hawkeye_app"
    )
    for role in _ROLES:
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {SCHEMA} FROM {role}")
        op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {SCHEMA} FROM {role}")
        op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM {role}")
    # Drop the roles last (only if not still granted to login users in dev).
    for role in _ROLES:
        op.execute(f"DROP ROLE IF EXISTS {role}")
