# `infra/storage/postgres/` — App/metadata DB (DATABASE-2)

> **Owner:** DATABASE. PostgreSQL 17.x holds the relational app/metadata:
> `users`, `cases` (+`case_notes`,`case_history`), `alerts_metadata`,
> `model_governance`, `approvals`, and the BACKEND-written re-id vault instance
> `pii_vault`. Alembic is the **DDL system-of-record**.
> Blueprint **Part 9.3** (l.363), **Part 28.2** (classification→access, l.1203).

## Schema + migrations
All tables live in the **`hawkeye`** Postgres schema (namespaced from PLATFORM's
`governance` DB and BACKEND's `public` objects). Migrations under
`db/postgres/migrations/versions/` — one reversible migration per logical unit:

| Rev | Tables |
|---|---|
| `0001_users` | `users` (8 RBAC roles, Part 24.1) |
| `0002_cases` | `cases`, `case_notes`, `case_history` |
| `0003_alerts_metadata` | `alerts_metadata` (relational mirror of ClickHouse `alerts`) |
| `0004_model_governance` | `model_governance`, `approvals` (four-eyes, SoD) |
| `0005_pii_vault` | `pii_vault` (re-id vault instance — ciphertext only) |
| `0006_roles_grants` | least-privilege roles + grants |

```bash
cd db/postgres
DATABASE_URL=postgresql+psycopg2://hawkeye:hawkeye_dev_pw@localhost:5432/hawkeye \
  alembic upgrade head        # apply
alembic downgrade base        # fully reversible
alembic upgrade head --sql    # offline: emit DDL, no DB (CI reversibility lint)
```

## Least-privilege roles (`0006_roles_grants`)
| Role | Grants | Note |
|---|---|---|
| `hawkeye_migrate` | DDL (ALL) | owns migrations; **never** the runtime role |
| `hawkeye_app` | DML on app tables + `pii_vault` | BACKEND runtime |
| `hawkeye_ro` | SELECT — **except `pii_vault`** | auditor / read paths; vault is need-to-know |

The app never runs as superuser. `pii_vault` read is REVOKED from `hawkeye_ro`:
unmask is a separate, audited capability (BACKEND.md §3) sealed to WORM.

## Encryption at rest + PII
- **At rest:** the data volume is an **encrypted volume** (LUKS locally; KMS-backed
  in prod — PLATFORM key custody, Part 9.3). Field-level PII is **already
  encrypted by BACKEND** before it reaches `pii_vault` (ciphertext only).
- **1:1 AWS swap:** RDS for PostgreSQL with storage encryption (KMS) +
  `pgcrypto`/field keys (`infra/terraform/modules/rds`, PLATFORM).

## Seam
DATABASE owns the instance + schema + roles + at-rest config. BACKEND writes
`pii_vault` (tokenizer + HMAC/field key, Vault custody) and the governance rows;
DATABASE never holds the real PII or the key.
