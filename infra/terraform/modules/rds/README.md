# Module: `rds` (PLATFORM-7) — SCAFFOLD

Managed **PostgreSQL 17.2** (BOM pin) for app/case metadata + the governance DB.

- Private only (`publicly_accessible = false`), **KMS-encrypted at rest**, **multi-AZ**
  for HA (Part 30), 7-day backups, deletion protection, Postgres logs to CloudWatch.
- **No password in Terraform:** `manage_master_user_password = true` puts the master
  secret in Secrets Manager — never inline (golden rule).
- **Blueprint:** Part 26.1 (App metadata DB → RDS PostgreSQL).
- **Migration (Part 26.4):** `RDS → self-hosted PostgreSQL 17.2`. Same engine version,
  so the schema/DDL (owned by DATABASE) ports unchanged. See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
