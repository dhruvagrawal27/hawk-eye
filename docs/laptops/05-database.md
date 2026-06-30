# Laptop 05 — DATABASE — Working Log

> Your **own** file. Decisions, files created, blueprint validations, deviations, blockers.
> Read `CONTEXT.md`, `BACKEND.md`, `TODO.md` first; append cross-cutting decisions to `CONTEXT.md`.
> Full brief: [prompts/05_DATABASE.md](../../prompts/05_DATABASE.md).

## Status
- Branch: `hawk-eye/database` · Owns: `db/`, `infra/storage/`, `infra/audit/`, `registry/`, `services/audit/`
- **All 9 tasks (DATABASE-1..9) REAL + tested.** Gates green: ruff · black · mypy · sqlfluff · pytest **60 passed / 10 integration skipped** (skip without live infra). Shell `bash -n`, `docker compose config`, XML + JSON + Avro all validate.

## Mandatory reading completed (blueprint line ranges validated against)
Part 8 (l.295-322 — ClickHouse analytics store, hot-cold tiering, inverted-index search, append-only Kafka audit + WORM, object-lock), Part 9.2 (l.350-360 — sharded+replicated CH, hot-cold, ~10-20× compression, Redis sizing), Part 9.3 (l.361-366 — append-only/WORM for alerts/dispositions/model-versions/feature-snapshots, field-level encryption, HSM, HA/DR), Part 19.2 (l.626 — encrypted+signed+access-logged registry), Part 19.3 (l.630-637 — tamper-evident audit of ALL activity incl. investigators), Part 21.5 (l.818-826 — partitioned-Parquet datasets, DVC content-hash, Feast offline, lineage), Part 23.1-23.4 (l.853-870 — formats, registry layout, security, serving load), Part 28.2 (l.1198-1208 — classification→retention, tiered hot→cold→archive DPDP/RBI). Also skimmed Part 5.1, 24.1/24.3, 10, 22.

## Decisions
- **ClickHouse engine toggle:** canonical DDL ships single-node `ReplacingMergeTree(ingested_at)` (runs on the storage compose with zero Keeper) = the documented "MergeTree fallback for single-node local dev"; `apply_ddl.sh CH_ENGINE_MODE=replicated` rewrites to `ReplicatedReplacingMergeTree` + `ON CLUSTER` (uses `default_replica_path`/`default_replica_name` from `cluster.xml`, so DDL needs no explicit zk args). Idempotency on `event_id` via ReplacingMergeTree + `ORDER BY (actor_employee_id, ts, event_id)`.
- **Money:** `object_amount`/`exposure_inr` = integer INR (CONTEXT.md §6); `Int64`.
- **Linkage:** the 6 named L0 linkage columns (faithful to BACKEND.md §1) PLUS a `linkage_extra Map(String,String)` for additive fields (BACKEND parses `extra=allow`).
- **reason_codes:** modeled as a ClickHouse `Nested(source, code, feature, detail, contribution)` (heterogeneous rule|shap|graph|sequence) + a flattened `reason_text` for the inverted index.
- **WORM hash scheme:** `record_hash = SHA-256(canonical_content ‖ 0x00 ‖ prev_hash)`; canonical = sorted-key compact JSON over content (excludes prev_hash/record_hash). Daily Merkle root = domain-separated binary tree (leaf=0x00‖h, node=0x01‖l‖r, duplicate-last on odd). Single-writer ⇒ total order ⇒ reproducible chain + root.
- **Registry signature:** Ed25519 detached over the SHA-256 manifest of every bundle file except `signature.sig`. `metadata.json.signature` is a STABLE pointer `"ed25519:detached:signature.sig"` (NOT the bytes — embedding bytes would be self-referential since the bundle includes metadata.json). Authoritative artifact = `signature.sig`, verified on load.
- **Audit envelope = single source of truth** in `services/audit/audit_schema.py`; the `.avsc` mirrors it (contract test enforces parity).
- **Retention WORM invariant:** the job refuses (raises + logs) any expiry that shortens an object-lock object below its lock; `audit-archive` may never set a finite expiry. `build_plan` runs the check before emitting any action.

## Files created (by task)
- **DATABASE-1:** `infra/storage/minio/bootstrap_minio.sh`, `policies/{models-writer,models-reader,datasets-rw,audit-writer,read-only-auditor}.json`, `terraform/{main.tf,README.md}`, `README.md`.
- **DATABASE-2:** `db/postgres/{alembic.ini,migrations/env.py,script.py.mako,versions/0001..0006*.py}`, `infra/storage/redis/{redis.conf,README.md}`, `infra/storage/postgres/README.md`.
- **DATABASE-3:** `db/clickhouse/ddl/{00_init,01_events,02_scores,03_alerts,04_dispositions,05_feature_backfill,06_reports}.sql`, `storage_configuration.xml` (+`.local.xml`), `cluster.xml`, `apply_ddl.sh`, `ddl/CLUSTER.md`.
- **DATABASE-4:** `db/clickhouse/{indexes.sql,materialize_indexes.sql,search_helpers.sql}`.
- **DATABASE-5:** `infra/audit/kafka/{audit_event.avsc,topics.yaml}`, `infra/audit/create_topics.sh`, `infra/audit/README.md`.
- **DATABASE-6:** `services/audit/{audit_schema.py,hashchain.py,worm_store.py,worm_writer.py,verify_cli.py,__init__.py,README.md}`.
- **DATABASE-7:** `registry/artifacts/{layout.md,serializer.py,store.py,__init__.py}`.
- **DATABASE-8:** `registry/mlflow/{config.py,signing.py,load_verify.py,access_log.py,__init__.py}`, `registry/{README.md,keys/.gitignore,keys/README.md}`.
- **DATABASE-9:** `db/retention/{policies.yaml,retention_job.py,clickhouse_ttl.sql}`.
- **Cross:** `infra/storage/docker-compose.storage.yml`, `.env.storage.example`, `infra/storage/README.md`, `db/{README.md,requirements.txt,pyproject.toml,.sqlfluff}`, `db/tests/**` (unit/contract + integration).

## Blueprint validation (Part → task → ✓ evidence)
| Requirement (Part·~line) | Task | Evidence |
|---|---|---|
| ClickHouse analytical store (8·305) | DB-3 | 5 tables + `report_outputs`; L0/L6 parity test |
| Hot-cold tiering (8·305,318; 9.2·357) | DB-3,9 | `storage_configuration.xml` tiered; `TTL … TO VOLUME`; integration `MOVE PARTITION → cold` |
| Inverted indices (8·305-306) | DB-4 | `full_text` + tokenbf/ngrambf/minmax; `search_helpers.sql` |
| Sharded+replicated + compression (9.2·357) | DB-3 | `cluster.xml` 2×2 + Keeper; ZSTD/Delta codecs |
| Redis online store (8·301;9.2·359) | DB-2 | `redis.conf` DB0/DB1, volatile-lru |
| WORM for alerts/dispositions/model-versions/feature-snapshots (9.3·364) | DB-6 | `worm_writer` seals all classes; verify PASS/FAIL test |
| Field-level encryption / at-rest; HSM swap (9.3·363) | DB-1,2 | SSE-S3 local KMS; KMS/HSM swap notes |
| Append-only Kafka audit + WORM (8·311) | DB-5,6 | `topics.yaml` retention.ms=-1; WORM sink |
| Tamper-evident audit incl. investigators (19.3·634) | DB-6 | view_entity/view_alert + rule_change + pii_unmask actions sealed |
| Model extraction mitigations (19.2·626) | DB-8 | signed+encrypted+least-priv+access-logged registry |
| Model formats: trees ONNX+native; nets ONNX+checkpoint; chain together (23.1·855) | DB-7 | whole-chain round-trip test (tree + net) |
| MLflow stages + per-version six fields + signature (23.2·860) | DB-8 | register six-field + stage; signing |
| Encrypted+object-lock+least-priv+verify-on-load+lifecycle (23.3·864) | DB-1,8,9 | verify-on-load reject test; object-lock buckets; lifecycle |
| Serving pulls Production + verifies; model_version per score (23.4·867) | DB-8,3 | `secure_load`; `scores.model_version` |
| Dataset storage + Parquet + DVC + lineage (21.5·823) | DB-1,3,8 | `datasets/{name}/dt=…/source=…`; content-hash; `feature_backfill`; `dataset_hash` |
| Retention tiering DPDP/RBI (28.2·1208) | DB-9 | `policies.yaml` windows + fraud carve-out |
| Classification drives retention (28.2·1203) | DB-9,1,2 | classification-aware windows; RBAC |
| DDL versioning / migrations | DB-2 | Alembic reversible; ClickHouse `apply_ddl.sh` + ordered DDL |

## Deviations / assumptions
- ClickHouse cold/archive tiers use **2 extra MinIO buckets** (`clickhouse-cold`, `clickhouse-archive`) beyond the 4 named app buckets — CH-internal tiering targets, documented. The 4 named buckets are the app contract.
- Added a `report_outputs` ClickHouse table (Reporting seam: BACKEND generates, DATABASE stores) + `case_notes`/`case_history` Postgres tables — additive, nothing dropped.
- `sqlfluff`'s clickhouse dialect (4.x) cannot parse `TTL … TO VOLUME`, `INDEX … TYPE full_text`, or parameterized-view `{param:Type}` (ClickHouse 25.x); `db/.sqlfluff` keeps layout+capitalisation rules active and tolerates these parser gaps (documented). CP02/CP03/CP05 disabled because ClickHouse type/function names are case-sensitive mixed-case.
- Local dev interpreter is 3.9 (unit tests run there); code targets/pins **3.12** (compose/CI). Kept 3.9-runnable via `from __future__ import annotations`.
- `ws_DATABASE.json` (task inventory) not present in the repo; cross-checked against prompt §6 inventory mapping instead (all 11 components covered).

## AWS ↔ on-prem swap notes
MinIO SSE-S3 (local KMS key) → S3 SSE-KMS (one config change); object-lock → S3 Object Lock COMPLIANCE; least-priv `mc` policies → IAM (same JSON). Postgres → RDS+KMS; Redis → ElastiCache (at-rest/in-transit KMS); ClickHouse cold/archive → S3 (`s3://…ap-south-1`), residency in-India. Kafka → MSK (same topic configs). MLflow artifact store → S3. Signing key → Vault/HSM or cosign. PLATFORM owns key custody + the cloud apply (Terraform stubs handed over).

## Performance
- Unit/contract suite: 60 tests in ~0.3s. Sub-second investigative-search budget (~1M rows) is exercised by the integration `test_clickhouse_flow` (skip without infra); skip-index + full-text pruning recorded when run with the storage compose.

## Blockers (mirror in TODO.md §7 + CONTEXT.md)
- None blocking. Reconciliation pending: DATA finalizing `data/schemas/l0_event` `.avsc`/`.proto` — `events` DDL already field-for-field with BACKEND.md §1 (marked `TODO reconcile`).

## Adversarial review (6 dimensions × per-finding verification) — 8 confirmed defects fixed
Ran a multi-agent review vs §9 gate + §6 acceptance; 10 raised, 8 confirmed, all fixed + regression-tested:
1. **[blocker] MinIO KMS key 35 bytes** (compose + .env) → MinIO FATAL on boot → whole M1 stack blocked. Fixed to a verified 32-byte key; **boot-tested live** (container Up, no FATAL).
2. **[major] search views wrapped indexed column in `lower()`** while indices were on the bare column → full scan. Moved the `hasToken` token/ngram indices onto `lower(payload)`/`lower(reason_text)`; **`EXPLAIN indexes=1` on live CH 25.3 now shows `idx_reason_tokens` pruning granules.**
3. **[major] WORM tail-truncation passed** (delete newest records before the day's anchor). Added chain-head reconciliation (authoritative length) + seq-contiguity. New tests.
4. **[major] WORM missing-anchor day skipped** verification. Days now derived from records; chain-head catches same-day truncation even with the anchor deleted. New test.
5. **[major] corrupt metadata.json → JSONDecodeError before audit + wrong exception.** `load_chain` now preserves exact stored bytes + tolerates bad JSON; `secure_load` always emits the access-log and rejects with `SignatureError`. New test.
6. **[major] retention TTL applier dropped every statement** (split-on-';' + startswith-'--' killed comment-prefixed ALTERs). Rewrote to strip comments first; **applied 6/6 live**. Also caught + fixed live: `MODIFY TTL` on full-text-indexed tables needs `allow_experimental_full_text_index` in-session (events/alerts/dispositions failed without it) → job now passes the setting; **6/6 apply clean**.
7. **[minor] replicated-mode `ON CLUSTER` not applied to CREATE VIEW** → views only on one node. Fixed the sed.
8. **[minor] null `merkle_root` crashed verify with TypeError** instead of FAIL. Guarded. New test.

**Live verification on pinned ClickHouse 25.3 + MinIO RELEASE.2024-12-18:** all 6 tables created with `storage_policy=tiered`; full_text + tokenbf(lower) + ngrambf(lower) indices present; parameterized search views return the seeded match (case-insensitive); **TTL-MOVE moved the aged `202601` partition to the `cold` volume** (`system.parts.disk_name='cold'`); MinIO boots with the corrected key. (Doc fix: parameterized views are called with function-arg syntax `view(employee='…', limit=N)`, not `--param_*` — corrected in `search_helpers.sql`.)

## Session log (newest first)
- 2026-06-30 — Built DATABASE-1..9 REAL on synthetic data; all §8 gates green (ruff/black/mypy/sqlfluff/pytest 64 +10 integration). Ran a 6-dimension adversarial review with per-finding verification (8 confirmed defects, all fixed + regression-tested); verified the storage tier live on pinned ClickHouse 25.3 + MinIO. Published contracts to CONTEXT.md; TODO.md §5 all `[x]`; cleared the DATA→DATABASE blocker.
