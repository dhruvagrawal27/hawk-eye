"""pii_vault — re-identification vault table INSTANCE (DATABASE-2)

SEAM (prompt §5, Part 25.3 / Part 19.3): BACKEND owns the tokenizer + the write
path + the HMAC key (PLATFORM custody). DATABASE provides ONLY the encrypted,
RBAC-restricted table instance. We store **ciphertext only** — never real PII
(golden rule 2). Every unmask is a separate audited capability (BACKEND.md §3,
`POST /entities/{id}/unmask`) sealed to WORM (DATABASE-6).

Field-level encryption: `ciphertext` is already-encrypted bytes (BACKEND encrypts
with the Vault-custodied field key); the table additionally lives on an
encrypted-at-rest volume (compose / KMS-backed volume in prod).

Revision ID: 0005_pii_vault
Revises: 0004_model_governance
Create Date: 2026-06-30

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_pii_vault"
down_revision = "0004_model_governance"
branch_labels = None
depends_on = None

SCHEMA = "hawkeye"


def upgrade() -> None:
    op.create_table(
        "pii_vault",
        # token = the de-identified surrogate BACKEND puts in alerts/events
        sa.Column(
            "token", sa.Text(), primary_key=True
        ),  # e.g. EMP-7f3a / ACCT-… / BEN-…
        sa.Column(
            "token_type", sa.Text(), nullable=False
        ),  # employee|account|beneficiary
        # ciphertext = field-level-encrypted real value (NEVER plaintext PII)
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column(
            "created_ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_pii_vault_type", "pii_vault", ["token_type"], schema=SCHEMA)
    # Document the invariant at the DB level (defence-in-depth comment).
    op.execute(
        f"COMMENT ON TABLE {SCHEMA}.pii_vault IS "
        "'Re-id vault INSTANCE (DATABASE-2). BACKEND-owned write path + HMAC/field "
        "key (Vault custody). Ciphertext only — never real PII. Read = audited "
        "unmask capability only (BACKEND.md §3). RBAC: hawkeye_app only; "
        "hawkeye_ro is REVOKED (need-to-know, see migration 0006).'"
    )


def downgrade() -> None:
    op.drop_index("ix_pii_vault_type", table_name="pii_vault", schema=SCHEMA)
    op.drop_table("pii_vault", schema=SCHEMA)
