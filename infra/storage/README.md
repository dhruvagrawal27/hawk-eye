# `infra/storage/` — Storage-tier compose + IaC stubs (DATABASE-1/2)

> **Owner:** DATABASE. Storage-specific compose + config + Terraform stubs for
> MinIO / Postgres / Redis / ClickHouse, plus the audit-topic bring-up (DATABASE-5).
> **Seam:** PLATFORM owns the global `infra/` runtime + the root compose; these
> modules are **includable** by PLATFORM's stack and runnable **standalone** for
> DATABASE dev (so we never block on the full stack). Ports = CONTEXT.md §7.

## Standalone bring-up
```bash
cp infra/storage/.env.storage.example infra/storage/.env.storage   # dev defaults
docker compose -f infra/storage/docker-compose.storage.yml --env-file infra/storage/.env.storage up -d
# with the append-only audit topic (DATABASE-5):
docker compose -f infra/storage/docker-compose.storage.yml --profile audit up -d
```
This runs the bootstrap one-shots automatically:
- `minio-setup` → 4 app buckets (+2 CH tiering) · versioning · object-lock · SSE · 5 least-priv policies (DATABASE-1)
- `pg-migrate` → `alembic upgrade head` (DATABASE-2)
- `ch-ddl` → 5 tables + tiering + inverted/skip indices + search views (DATABASE-3/4)
- `audit-topics` (profile `audit`) → append-only `hawkeye.audit` (DATABASE-5)

## Layout
```
infra/storage/
  docker-compose.storage.yml      # the standalone stack
  .env.storage.example            # dev env (mirrors repo .env.example + BOM pins)
  minio/      bootstrap_minio.sh · policies/*.json · terraform/ (stub) · README
  postgres/   README (schema+roles+at-rest; migrations live in db/postgres)
  redis/      redis.conf · README (keyspace DB0 online / DB1 cache)
```

## Seam with PLATFORM (don't double-run)
- PLATFORM's `make core-up` already starts MinIO/Postgres/Redis/ClickHouse with the
  same ports + creds (`deploy/compose/docker-compose.core.yml`). To bind DATABASE's
  schema/buckets onto **that** stack instead of this standalone one, run the
  bootstrap scripts against it:
  ```bash
  MINIO_ENDPOINT=http://localhost:9001 ./infra/storage/minio/bootstrap_minio.sh
  CH_HOST=localhost ./db/clickhouse/apply_ddl.sh --materialize
  (cd db/postgres && DATABASE_URL=postgresql+psycopg2://hawkeye:hawkeye_dev_pw@localhost:5432/hawkeye alembic upgrade head)
  ```
- Terraform stubs (`minio/terraform/`) are **plan-only** and consumed by PLATFORM's
  global stack for the AWS apply. Do not edit PLATFORM's networking/root compose.

## Encryption-at-rest + AWS swap (summary; details in each sub-README)
| Store | At rest (dev) | AWS swap |
|---|---|---|
| MinIO | SSE-S3 (local KMS key) | S3 + SSE-KMS + Object Lock |
| Postgres | encrypted volume | RDS + KMS storage encryption |
| Redis | encrypted volume (RDB/AOF) | ElastiCache + at-rest/in-transit KMS |
| ClickHouse | encrypted volume; cold/archive on MinIO | self-managed CH / CH Cloud, in-India |

Key custody (Vault/HSM) is PLATFORM's seam (Part 9.3); DATABASE wires the local
key for dev and documents the one-line swap.
