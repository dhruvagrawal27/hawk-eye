# `db/` — Hawk-Eye DATABASE workstream (Laptop 05)

> The full persistence substrate every other workstream writes to and reads from.
> **ALERT-ONLY · on-prem · synthetic-only.** Storage never carries an auto-block
> decision; the WORM audit + signed registry exist so a *human* decision is always
> reconstructable and defensible. Built REAL on MinIO/Postgres/Redis/ClickHouse,
> 1:1-swappable to AWS managed services. Brief: [`prompts/05_DATABASE.md`](../prompts/05_DATABASE.md).

## What DATABASE owns (and where it lives)
| Area | Path | Tasks |
|---|---|---|
| ClickHouse analytics/investigation store + tiering + search | `db/clickhouse/` | DATABASE-3/4 |
| Postgres app/metadata DB + Alembic migrations + roles | `db/postgres/` | DATABASE-2 |
| Retention & archival tiering (hot→cold→archive) | `db/retention/` | DATABASE-9 |
| Object store (MinIO) buckets/SSE/object-lock/RBAC + dataset layout | `infra/storage/minio/` | DATABASE-1 |
| Storage-tier compose + Redis/Postgres config | `infra/storage/` | DATABASE-1/2 |
| Append-only Kafka audit topic + producer schema | `infra/audit/` | DATABASE-5 |
| WORM writer + hash-chain/Merkle + verify CLI | `services/audit/` | DATABASE-6 |
| Signed model-file registry layout/serializer/signing/verify/access-log | `registry/` | DATABASE-7/8 |

## Pinned versions (blueprint Part 24.3 / BACKEND.md §0 / deploy/versions.bom.yaml)
| Component | Pin | Component | Pin |
|---|---|---|---|
| ClickHouse | `25.3` | MLflow | `2.18` |
| PostgreSQL | `17.2` | Alembic / SQLAlchemy | `1.13+` / `2.0.x` |
| Redis | `7.4.1` | cryptography (Ed25519) | `>=42` |
| MinIO | `RELEASE.2024-12-18T13-15-44Z` | Python | `3.12.x` |
| Kafka | `3.8.1` | Docker / Terraform | `27` / `1.9` |
Python tooling pinned in [`db/requirements.txt`](requirements.txt). No floating
`latest` (MinIO release tag pinned too).

## ClickHouse (DATABASE-3/4) — `db/clickhouse/`
5 investigation tables mirror the contracts **field-for-field**:
- `events` ↔ BACKEND.md §1 (L0 Actor/Action/Object/Context/Linkage)
- `scores` (per-layer L1..L6 + fused; `model_version` on every row, Part 23.4)
- `alerts` ↔ BACKEND.md §2 (L6 alert) · `dispositions` ↔ BACKEND.md §5 (EDD→label)
- `feature_backfill` (offline, identical defs to online → no train/serve skew)
- (+ `report_outputs`, the reporting-seam store)

**Hot-cold tiering** (`storage_configuration.xml`): `default`(hot SSD) → `cold`
(MinIO) → `archive` (MinIO), policy `tiered`, `TTL … TO VOLUME` at 30d/365d.
**Cluster** (`cluster.xml`): 2 shards × 2 replicas, ReplicatedReplacingMergeTree +
Keeper (apply with `CH_ENGINE_MODE=replicated`; single-node default for dev).
**Search** (DATABASE-4): inverted (full-text) indices on `payload`/`reason_text` +
`tokenbf_v1`/`ngrambf_v1`/`bloom_filter`/`minmax` skip indices; parameterized
search views in `search_helpers.sql` (by employee/IP/device/beneficiary/free-text
+ entity-360 timeline). Apply: `db/clickhouse/apply_ddl.sh [--materialize]`.

## Postgres (DATABASE-2) — `db/postgres/`
Schema `hawkeye`; tables `users`, `cases`(+`case_notes`,`case_history`),
`alerts_metadata`, `model_governance`, `approvals`, `pii_vault` (re-id vault
INSTANCE — ciphertext only; BACKEND owns the write path + key). Alembic is the
DDL system-of-record (`alembic upgrade head` / `downgrade base`, fully reversible).
Least-privilege roles `hawkeye_migrate`/`hawkeye_app`/`hawkeye_ro` (`pii_vault`
read REVOKED from `hawkeye_ro` — unmask is a separate audited capability).

## Redis (DATABASE-2) — `infra/storage/redis/`
DB0 = Feast online (`<entity>:<feature>:<window>`), DB1 = cache; AOF+RDB; at-rest
on an encrypted volume.

## Object store (DATABASE-1) — `infra/storage/minio/`
Buckets `models`*, `datasets`, `feature-snapshots`, `audit-archive`* (*=object-lock
+versioned), SSE-S3 at rest, 5 least-privilege policies (no `*`). Dataset layout
`datasets/{name}/dt=YYYY-MM-DD/source={src}/part-*.parquet` (+ content-hash sidecar;
DVC remote = `s3://datasets`).

## WORM audit (DATABASE-5/6) — `infra/audit/`, `services/audit/`
Append-only `hawkeye.audit` topic (`cleanup.policy=delete`, `retention.ms=-1`,
compaction off). The WORM writer drains it, **hash-chains** each record
(`record_hash = H(content ‖ prev_hash)`) + a **daily Merkle root**, and seals
immutably to the object-lock `audit-archive` bucket. `verify_cli.py` re-walks the
chain + roots → **PASS**/**FAIL**. Covers all six record classes + investigators'
own actions + registry access.
```bash
python -m services.audit.verify_cli                  # verify the live store
python -m services.audit.verify_cli --local ./copy   # verify a (tampered) copy
```

## Model registry (DATABASE-7/8) — `registry/`
`models/{layer}/{model}/{version}/` with `model.onnx` + native booster +
`transform_chain/` + `calibrator.joblib` (+`checkpoint.pt` for nets) +
`metadata.json` (six fields: dataset_hash/params/metrics/training_code_commit/
approver/signature) + `signature.sig` (Ed25519 detached over the bundle). Stages
`Staging→Production→Archived`; **verify-on-load rejects tampered artifacts**; every
read/load/promote is access-logged to WORM. See [`registry/README.md`](../registry/README.md).

## Retention (DATABASE-9) — `db/retention/`
`policies.yaml` (DPDP/RBI windows, classification-aware, fraud carve-out) +
`retention_job.py` (plan/apply: ClickHouse TTL-MOVE, MinIO lifecycle, WORM-safe).
**Hard invariant:** never expire/shorten an object-lock object below its lock.
```bash
python -m db.retention.retention_job          # plan
python -m db.retention.retention_job --apply  # apply (needs live stores)
```

## Encryption-at-rest stance (Part 9.3) + AWS swap
MinIO **SSE-S3** (local KMS key) → flip to **SSE-KMS** by pointing the KMS at
Vault/KES (one config change). Postgres/Redis/ClickHouse at rest on encrypted
volumes → KMS/HSM-backed in prod. **PLATFORM owns key custody**; DATABASE wires the
local key for dev and documents every 1:1 swap. Residency stays **in-India**.

## Build / test (see §8 of the prompt)
```bash
pip install -r db/requirements.txt
ruff check db registry services/audit && black --check db registry services/audit && mypy db registry services/audit
sqlfluff lint db/clickhouse db/postgres
pytest db/tests -q                                   # unit + contract
docker compose -f infra/storage/docker-compose.storage.yml up -d
pytest db/tests/integration -q                       # cross-store flows
```
Published contracts (DDLs, buckets, keyspace, audit schema, registry layout,
retention windows) live in **CONTEXT.md** (INTEGRATION LOG) for the other laptops.
