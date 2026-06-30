# Hawk-Eye — Laptop 05: DATABASE — Claude Code Build Prompt

> You are the **DATABASE** laptop. You build the entire persistence layer of Hawk-Eye and merge into a shared git repo alongside 5 other laptops (DATA, ML, BACKEND, FRONTEND, PLATFORM). This prompt is your single source of truth for *what to build, how, and in what order*. It is exhaustive on purpose. Read it top to bottom before writing a line of code, then keep it open.

---

## 0. Mission & golden rules

**Mission.** Deliver the full persistence substrate every other workstream writes to and reads from:
- **MinIO/S3 object store** (models, datasets, feature-snapshots, audit-archive) — encrypted-at-rest, versioned, object-locked.
- **PostgreSQL** application/metadata DB (cases, users, alerts metadata, model-governance, approvals) via versioned migrations.
- **Redis** online feature/cache store config (the physical store Feast online + the inference hot path read).
- **ClickHouse** columnar analytics/investigation store (canonical events, scores, alerts, dispositions, feature backfill) with **hot-cold tiering** and **inverted-index search**.
- **Append-only Kafka audit topics + WORM/object-lock immutable audit trail** with hash-chaining/Merkle anchoring — tamper-evident, regulator-grade, covering investigators' own actions.
- **MLflow-backed signed model-file registry** with the `{layer}/{model}/{version}/` object-store layout, full reproducibility metadata, and signature-verified loads.
- **DPDP/RBI-aligned retention & archival tiering** (hot ClickHouse → cold object store → archive).

Everything is **REAL on synthetic data** with on-prem-equivalent components (MinIO for S3, local KMS/Vault for keys), swappable 1:1 to AWS managed services later. All 9 DATABASE tasks are REAL — no SCAFFOLD, no MOCK.

**Golden rules (restate to yourself every session; these are non-negotiable):**
1. **ALERT-ONLY.** The system scores and explains; a human decides. Storage must never carry an auto-block decision. Your WORM audit and registry exist so a human decision is always reconstructable and defensible — never to enable an automatic action.
2. **ON-PREM + SYNTHETIC ONLY.** No real PII, no real bank feeds, no real cloud creds, no real KMS/HSM/AWS account. Use MinIO (S3-compatible), local SSE keys / Vault / a local KMS shim, and synthetic data from the DATA simulator. Where a line in the blueprint names a cloud-only primitive (S3 SSE-KMS, AWS object-lock compliance mode), implement the **MinIO on-prem equivalent** that is fully runnable locally and document the 1:1 AWS swap. Your tasks stay REAL because the MinIO equivalent is buildable; do not mark them SCAFFOLD.
3. **VALIDATE AGAINST THE BLUEPRINT.** No task is "done" until the matching blueprint Part's requirement is demonstrably met. Cite the Part in every commit and in your laptop log. See §9 for the validation gate.
4. **NOTHING DROPPED.** Every item in your task inventory and every must-cover capability (§6) must be built. If you find a blueprint storage requirement that is in nobody's lane, raise it in `CONTEXT.md` immediately and tag the likely owner.
5. **STAY IN YOUR LANE.** Edit only files under `db/` (plus the storage-adjacent dirs explicitly assigned below: `infra/storage/`, `infra/audit/`, `registry/`, `services/audit/` — see §3 for the exact list and the seam note), your own laptop log `docs/laptops/05-database.md`, and **append-only** to the shared MD files. Never edit another laptop's owned code or rewrite `BACKEND.md`.

---

## 1. Mandatory reading before any code

Read these in this order, every session, before touching code:

1. **Blueprint — the parts you OWN (read in full):** `Insider_Fraud_Detection_Implementation_Blueprint (2).md`
   - **Part 8** — Technology stack: ClickHouse as the analytical/investigation store, hot-cold tiering, inverted indices for search, audit/immutability via append-only Kafka topics + WORM storage (~l.295–320, esp. l.305–311, 317–318).
   - **Part 9.2** — Sizing (Kafka brokers, Flink TMs, ClickHouse sharded+replicated cluster with hot-cold tiering, Redis sizing) (~l.353–360).
   - **Part 9.3** — Security/residency/resilience: append-only/WORM for alerts, dispositions, model versions, feature snapshots; field-level encryption; HSM for keys; HA/DR multi-rack/DC replication, RPO/RTO, restore drills (~l.361–366).
   - **Part 19.2** — Model extraction/theft mitigations: encrypted-at-rest signed artifacts, access-controlled registry, registry access logging (~l.626).
   - **Part 19.3** — Tamper-evident audit (quis custodiet): append-only/WORM logging of *all* activity including investigators' own actions (who viewed whom, who closed which alert, who changed a rule/threshold) (~l.630–637).
   - **Part 21.5** — Dataset storage & versioning: ClickHouse + object store partitioned Parquet (by date/source), curated sets versioned with DVC/MLflow data artifacts + content hash, Feast offline store, dataset-hash + feature-set-version lineage per model (~l.822–826).
   - **Part 23** — How model files are stored: formats (trees → ONNX + native `.txt`/`.cbm`/joblib; nets → ONNX + PyTorch checkpoint; preprocessors/transformers/calibrators versioned together as the whole transform chain), MLflow registry layout `s3://.../{layer}/{model}/{version}/` with dataset hash/params/metrics/code-commit/approver/signature, encryption-at-rest + object-lock + least-privilege + model signing verified on load + lifecycle archival, serving load path (~l.853–870).
   - **Part 28.2** — Retention & archival tiering aligned to DPDP/RBI; also data classification (PII/PAN/sensitive vs operational) that drives masking/access/**retention** (~l.1208 and l.1201–1208).
2. **Blueprint — skim the rest** so you understand the seams: Part 5.1 (L0 event field groups — your ClickHouse tables mirror this), Part 24.1/24.3 (RBAC roles + pinned versions), Part 10 (MLOps / registry / feedback loop consumers of your stores), Part 22 (how models are trained — explains the artifacts you must store).
3. **`BUILD_PLAN.md`** — read the **DATABASE** workstream section (M1–M5, tasks DATABASE-1..9) and the cross-workstream dependency notes. Skim the other workstreams' sections to know who consumes your stores.
4. **The 3 shared MD files (every session, in this order):**
   - **`CONTEXT.md`** — shared brain. Read §4 (ownership), §5–6 (contracts live in BACKEND.md; conventions: IDs, time, money, branch/commit format), §7 (ports/service map — **ClickHouse 8123/9000, Redis 6379, Postgres 5432, MinIO 9001/9002 are YOURS**; MLflow 5000 is ML-owned), and the **INTEGRATION LOG** at the bottom (newest first).
   - **`BACKEND.md`** — the integration contract you READ (you do not own it). Note the **L0 event JSON** (§1), the **L6 alert JSON** (§2 — drives your ClickHouse `alerts` table + Postgres alert metadata), the **EDD disposition payload** (§5 — drives your `dispositions` table + label rows + `audit_id`), the **pinned versions** (§0), and the model-serving/narrative audit-memo shapes (§6–7 — narrative audit memo fields you persist to WORM).
   - **`TODO.md`** — keep **section 5 (DATABASE)** rows current as you progress; put cross-laptop blockers in §7.
5. **`README.md`** — repo layout, golden rules, merge model.
6. **Your task inventory JSON** (read every item): `ws_DATABASE.json`. Every component there maps to a task in §6 — cross-check before you call yourself done.

Log in `docs/laptops/05-database.md` that you completed this reading, with the blueprint line ranges you validated against.

---

## 2. The MD-file coordination protocol (the 4 files — exact read/write rules)

There are **four kinds** of MD files. Obey these rules precisely.

| File | Who owns | Your action | Rule |
|---|---|---|---|
| **`CONTEXT.md`** | Shared (everyone appends) | **Read first every session; append** | Append cross-cutting decisions/interfaces to the **INTEGRATION LOG** at the bottom, **newest first**. Never edit or delete others' entries. |
| **`BACKEND.md`** | **BACKEND laptop owns it** | **Read only** | This is the contract you integrate against (event/alert/disposition schemas, RBAC, audit-memo shape). You **never** write to it. If you need a contract change (e.g., a new alert field you must store), propose it in `CONTEXT.md` and **tag BACKEND**. |
| **`TODO.md`** | Shared board | **Keep your rows current** | Update **section 5 (DATABASE)** statuses (`[ ]` todo, `[~]` in-progress, `[x]` done, `[!]` blocked). A row is `[x]` only when its blueprint requirement is validated. Cross-laptop blockers go in §7. |
| **`docs/laptops/05-database.md`** | **You own it** | **Maintain continuously** | Your working log: decisions, files created, blueprint validations (with Part + line cite), deviations from blueprint (with rationale), blockers, and the AWS↔on-prem swap notes. |

**Ownership of BACKEND.md — restate:** The **BACKEND laptop owns `BACKEND.md`**. Everyone else (including you) READS it to integrate. You do not edit it.

**When to append to CONTEXT.md (do it as you go, not at the end):**
- Any DDL/table name, column, or partition key other laptops bind to (events/scores/alerts/dispositions/feature-backfill table shapes).
- The object-store bucket names + path conventions (especially the model-registry layout `{layer}/{model}/{version}/` and the partitioned-Parquet dataset layout).
- Redis keyspace/DB-index conventions and the online-store encryption note (DATA/ML/BACKEND read Redis).
- The WORM audit event schema + the hash-chaining/Merkle anchoring scheme and the verification CLI invocation.
- Retention windows you pick (TTL values, archive tiers) and the DPDP/RBI rationale.
- The encryption-at-rest approach (MinIO SSE vs SSE-KMS) and the local-KMS/Vault swap note.
- Any deviation from the blueprint, with the Part cited and the reason.

Use the CONTEXT.md log format: `### YYYY-MM-DD — [DATABASE] — title` then a short note.

**Append-first sample entry to write at start:**
```
### 2026-06-30 — [DATABASE] — Storage layout + bucket/keyspace conventions published
ClickHouse tables: events, scores, alerts, dispositions, feature_backfill (MergeTree, partition by toYYYYMM(ts), hot SSD → cold object-store via TTL MOVE). MinIO buckets: models, datasets, feature-snapshots, audit-archive (all versioned+object-lock). Model registry path: {bucket=models}/{layer}/{model}/{version}/. Redis: DB0 Feast online, DB1 cache. WORM audit hash-chained per record + daily Merkle root. Details in db/README.md.
```

---

## 3. Ownership, directories & git/merge discipline

**Branch:** `hawk-eye/database` (create from `main`; never commit to `main`).

**Commit message format (mandatory):**
```
[DATABASE] DATABASE-3 ClickHouse MergeTree events table + hot-cold TTL-MOVE tiering (blueprint Part 8, 9.2)
```
Always: `[DATABASE] <TASK-ID> <message> (blueprint Part X[, Y])`. Cite the Part(s) the commit satisfies.

**Directories you OWN and may edit:**
- `db/` — your primary home: `db/clickhouse/`, `db/retention/`, plus a top-level `db/README.md` describing everything you ship.
- `infra/storage/` — MinIO/Postgres/Redis compose + terraform-module stubs for the storage tier (DATABASE-1, DATABASE-2). *(Seam note: PLATFORM owns the overall `infra/` runtime and the root compose. Your `infra/storage/` modules are storage-specific and must be includable by PLATFORM's stack. Coordinate ports per CONTEXT.md §7 and the deploy convention in CONTEXT.md; do not edit PLATFORM's networking or root compose.)*
- `infra/audit/` — append-only Kafka audit-topic config (DATABASE-5). *(Seam note: DATA/PLATFORM own the Kafka cluster itself; you only define the audit topics' config + producer schema. Reference DATA's Kafka cluster, do not re-provision it.)*
- `registry/` — `registry/artifacts/` (model file-format + transform-chain layout, DATABASE-7) and `registry/mlflow/` (MLflow registry config/helpers: signing, encryption, access logging, DATABASE-8). *(Seam note below.)*
- `services/audit/` — the WORM writer/sink, hash-chaining/Merkle anchoring, verification CLI (DATABASE-6).
- `docs/laptops/05-database.md` — your log.
- **Append-only** to `CONTEXT.md`, `TODO.md`.

**Do NOT touch:** `data/`, `ml/`, `backend/`, `frontend/`, `platform/`, `.github/`, the root `docker-compose.yml`, `BACKEND.md`, other laptops' logs, or `pipelines/`/`mlops/`/`feature_store/`/`schemas/` (those are DATA/ML/BACKEND).

**Seam clarifications baked into your dirs (see §5 for the full seam table):**
- **Model storage/registry is split:** *you (DATABASE) own the object-store + registry LAYOUT, buckets, encryption, object-lock, signing-at-rest, and access logging.* **ML owns the MLflow *tracking server* runtime + the ONNX packaging/signing that happens during training.** Your `registry/mlflow/` is the **storage/layout config + load-time signature-verification + access-logging helpers**, not the training-time tracking server (that is ML/PLATFORM). Keep your code consuming the artifacts ML produces; expose the layout + verification utilities ML and BACKEND call. Publish the bucket/path contract in CONTEXT.md so ML packages into the exact paths.
- **Audit/WORM:** *you own the immutable/WORM store + the audit-topic config + the WORM writer/verifier.* **BACKEND writes audit events** (who-viewed-whom, alert closes, rule changes) onto the Kafka audit topic; everyone's actions (incl. investigators) are audited. You consume that topic and seal it to WORM. Do not implement BACKEND's audit-write call; provide the topic + producer schema contract.

**Stubbing not-yet-built upstream dependencies (so you never block):**
- **DATA-1 L0 event schema** (your ClickHouse `events` table mirrors it): if DATA hasn't published the final `.avsc`/`.proto`, build your DDL from the **L0 event JSON in `BACKEND.md` §1** (it is the agreed contract) and add a `-- TODO reconcile with data/schemas/l0_event once published (CONTEXT.md)` comment. When DATA finalizes, reconcile and note it in your log.
- **DATA Kafka cluster** (audit topics): your `infra/audit/` config references the Kafka bootstrap from CONTEXT.md §7 (`localhost:9092`); if not up, ship the topic-creation script + producer schema and a local single-broker Redpanda fallback in your own compose for testing.
- **PLATFORM base infra / Terraform scaffolding:** your `infra/storage/` modules must run standalone via your own compose for local dev; mark the Terraform pieces as includable by PLATFORM later.
- **ML model artifacts** (registry tests): generate a tiny **synthetic dummy artifact** (a trivial ONNX + a fake `.txt` booster + a fake calibrator joblib + a sidecar `metadata.json`) under a test fixtures dir to exercise the registry layout, signing, signature-verify-on-load, and access logging end-to-end. Never depend on a real trained model to test storage.

Stub, never block. Document every stub in your log and reconcile when the real dependency lands.

---

## 4. Tech stack & pinned versions (this workstream)

Pin to **blueprint Part 24.3** versions (mirrored in `BACKEND.md` §0). **Verify the latest patch of the pinned minor before locking**, then freeze in `db/README.md` and your compose/requirements.

| Component | Pinned (minor) | Role in your workstream |
|---|---|---|
| **ClickHouse** | **25.x** | Columnar analytics/investigation store; hot-cold tiering; inverted (full-text) + bloom/skip indices. |
| **PostgreSQL** | **17.x** | App/metadata DB: cases, users, alerts metadata, model-governance, approvals. |
| **Redis** | **7.4.x** | Online feature store (Feast online) + cache; encryption-at-rest config. |
| **MinIO** | latest stable (S3-compatible) | Object store: models, datasets, feature-snapshots, audit-archive; SSE, versioning, object-lock. |
| **Apache Kafka / Redpanda** | **Kafka 3.8.x** (Redpanda-compatible) | Append-only audit topics (config only; cluster owned by DATA/PLATFORM). |
| **MLflow** | **2.18** | Model Registry stages (Staging→Production→Archived); you own the storage/layout/signing/access-log config (tracking server runtime is ML/PLATFORM). |
| **Alembic** | matched to SQLAlchemy 2.x / Python 3.12.x | Postgres DDL versioning/migrations. |
| **cosign / sigstore** (or `cryptography`-based detached signature) | latest stable | Model signing; signature verified on load. Use a local key for on-prem (no cloud KMS). |
| **DVC** | latest stable | Curated dataset versioning + content hash (object-store remote = MinIO). |
| **Python** | **3.12.x** | Migration runner, WORM writer/verifier, registry helpers, retention job. |
| **Docker Compose / Terraform** | **Docker 27 / Terraform 1.9** | Local stack + IaC module stubs (Terraform = `plan`-only stubs; PLATFORM applies). |
| **Local KMS / Vault shim** | — | On-prem stand-in for SSE-KMS / HSM key custody (PLATFORM owns the real Vault/HSM-mock; you wire to a local key for dev). |

**Encryption-at-rest stance:** Use **MinIO SSE-S3 / SSE-C with a local key** as the on-prem equivalent of S3 SSE-KMS; structure config so flipping to SSE-KMS (cloud) is a one-line change. For Postgres/ClickHouse/Redis at-rest, configure disk/volume encryption notes + (where supported) the engine's at-rest encryption settings; document the swap to KMS/HSM-managed keys (PLATFORM owns the key custody seam).

---

## 5. Interface contracts / the seams (what you consume & produce)

**Reference `BACKEND.md` for all canonical contracts.** You consume those shapes and produce storage that conforms to them. Below is your full seam map — for any requirement sitting at a seam, your job is named explicitly and you must still mention/integrate it even if another laptop owns the primary build.

| Seam | Who owns the primary build | YOUR (DATABASE) responsibility |
|---|---|---|
| **L0 event schema** | **DATA owns** | Mirror it exactly in the ClickHouse `events` table (Actor/Action/Object/Context/Linkage field groups). Consume from `BACKEND.md` §1 until DATA's `.avsc`/`.proto` is final, then reconcile. |
| **L1 rules/BRE + SoD/toxic-combination matrix** | **BACKEND owns engine; DATA supplies stream** | You store nothing of the rule logic; you store rule/threshold **change records** (for audit, via the WORM trail) and the alerts/scores the engine emits. |
| **Feature store (Feast/Redis)** | **DATA defines & materializes features; ML & BACKEND read** | You provide the **physical Redis** instance + encryption-at-rest config + keyspace conventions (DATABASE-2) and the **ClickHouse offline feature-backfill** table (DATABASE-3) DATA writes to. You do not define feature logic. |
| **Models L2–L6 + L6 stacked meta-learner + calibrator** | **ML trains/produces artifacts; BACKEND runs online fusion/serving** | You store the artifacts (the whole transform chain) at the registry layout, signed + encrypted + object-locked (DATABASE-7/8). |
| **Model storage/registry** | **SPLIT — you own object-store + registry layout + buckets; ML owns MLflow tracking + ONNX packaging/signing** | Own the bucket layout `{layer}/{model}/{version}/`, encryption, object-lock, signature-verify-on-load, access logging, lifecycle. Publish the path contract so ML packages into it. |
| **LLM narrative gateway** | **ML owns client/prompt/fallback; BACKEND exposes `POST /narratives`; PLATFORM owns egress + TEE-mock** | You store the **narrative audit memo** (provider, tee_attested, attestation_id, model, prompt_hash, ts — `BACKEND.md` §7) to the **WORM** trail. You do not call the LLM. |
| **PII tokenization** | **BACKEND owns tokenizer + re-id vault; PLATFORM owns HMAC key/secrets** | Store **only tokenized** PII in ClickHouse/object store/audit (`pii_tokenized:true`). The re-id vault mapping lives in Postgres **owned/written by BACKEND**; you provide the Postgres instance + at-rest encryption + RBAC, never the real PII. Every unmask is an audited event you seal to WORM. |
| **Reporting (FMR/CRILC/EWS/RFA)** | **BACKEND generates; FRONTEND exports UI; DATABASE stores outputs** | You **store the report outputs** (object store + ClickHouse/Postgres metadata) and their retention class. You don't generate reports. |
| **Audit/WORM** | **DATABASE owns the immutable/WORM store; BACKEND writes audit events** | You own the WORM store, audit-topic config, writer, hash-chaining/Merkle anchoring, and verification CLI. Everyone's actions (incl. investigators) are audited. BACKEND emits the events; you seal them immutably. |
| **Source connectors** | **DATA owns adapters; PLATFORM owns integration runtime** | None directly — connectors land events into Kafka/ClickHouse; you just provide the `events` table sink target. |
| **Governance evidence** | **ML produces real model cards/validation evidence; PLATFORM produces process MOCKS** | You **store** model-governance rows in Postgres (model_governance, approvals) and model cards/validation reports as registry artifacts; you don't author them. |
| **Testing** | **Each laptop owns its own unit/contract tests; PLATFORM owns the cross-WS integration harness + CI** | You own `db/`-local unit/contract tests (DDL applies, migrations, WORM verify, registry round-trip, retention TTL). Contribute fixtures to PLATFORM's integration harness; don't own it. |

**What you CONSUME (inputs):** L0 event JSON + L6 alert JSON + disposition payload + narrative audit-memo shape (all from `BACKEND.md`); Kafka bootstrap + ports (CONTEXT.md §7); ML's packaged model artifacts (into your registry layout); DATA's feature-backfill writes.

**What you PRODUCE (outputs other laptops bind to — publish each in CONTEXT.md):** ClickHouse table DDLs + inverted-index search helpers; Postgres schemas + Alembic migrations; Redis instance + keyspace/encryption config; MinIO buckets + path conventions; the model-registry layout + signing/verify/access-log helpers; the WORM audit event schema + verification CLI; the retention/archival policy windows.

---

## 6. Your complete task list (every task, grouped by milestone)

Status legend: **REAL** = works as real code on synthetic/mock data locally. (All 9 DATABASE tasks are REAL.)
Columns: **ID · what · deliverable path · status · blueprint ref · acceptance check.** Every inventory-JSON component and every must-cover capability is mapped here — see the mapping notes.

### M1 — Core stores & encryption foundations
*Stand up the primary datastores (object store, Postgres, Redis) with encryption-at-rest and least-privilege access — the substrate every other workstream writes to.*

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **DATABASE-1** | **Object store (MinIO/S3)** with encryption-at-rest, versioning, object-lock-capable buckets, least-privilege RBAC. Buckets: `models`, `datasets`, `feature-snapshots`, `audit-archive`. SSE (SSE-S3/SSE-C local key; SSE-KMS swap documented). | `infra/storage/minio/` (compose + terraform module stub) + `db/README.md` bucket spec | REAL | Part 23.3 (l.864–865); Part 21.5 (l.823–824); Part 9.3 (l.363–364) | `docker compose up` brings MinIO online on 9001/9002; all 4 buckets exist with **versioning ON** and **object-lock ON** (for `models` + `audit-archive`); a PUT then overwrite shows version history; SSE encrypts at rest (object metadata shows encryption); a least-privilege policy denies a read-only principal a write. Publish bucket/path contract in CONTEXT.md. |
| **DATABASE-2** | **Postgres app/metadata DB + Redis online store.** Postgres schemas: `cases`, `users`, `alerts_metadata`, `model_governance`, `approvals` (+ the BACKEND-owned re-id vault table *instance*, not its real data). Alembic migrations. Redis for Feast online serving + cache, encryption-at-rest config + keyspace convention (DB0 online / DB1 cache). | `infra/storage/postgres/`, `infra/storage/redis/`, `db/postgres/migrations/` (Alembic) | REAL | Part 9.3 (l.363); Part 8 (Feast+Redis, l.301); Part 28.2 (classification→access, l.1203) | Postgres up on 5432; `alembic upgrade head` creates all schemas idempotently and `alembic downgrade` is reversible; Redis up on 6379 with at-rest config + the two DB indices documented; least-privilege Postgres roles (app vs read-only vs migration) enforced; CONTEXT.md updated with schema + keyspace conventions. |

### M2 — ClickHouse analytics & investigation store
*The columnar history/investigation store the event model, features, scores, alerts and dashboard query — with hot-cold tiering and log search.*

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **DATABASE-3** | **ClickHouse columnar store with hot-cold tiering.** MergeTree tables: `events` (mirrors L0 Actor/Action/Object/Context/Linkage), `scores` (per-layer + fused scores history with `model_version`), `alerts` (mirrors L6 alert JSON), `dispositions` (EDD outcomes → labels with `audit_id`), `feature_backfill` (offline feature defs, identical to online to avoid skew). `storage_configuration.xml` with **hot (SSD) / cold (object-store) volume policy** and **TTL … TO VOLUME** (TTL-MOVE) tiering (~14–30 days hot). Sharded+replicated cluster config (ReplicatedMergeTree + cluster macros), heavy compression. | `db/clickhouse/ddl/*.sql`, `db/clickhouse/storage_configuration.xml`, `db/clickhouse/cluster.xml` | REAL | Part 8 (analytics store + hot-cold tiering, l.305, 317–318); Part 9.2 (sharded+replicated, hot-cold, ~10–20× compression, l.357); Part 5.1 (event field groups via BACKEND.md §1) | ClickHouse up on 8123/9000; all 5 tables create cleanly and mirror the L0/L6 contracts (column-for-column vs BACKEND.md §1/§2); inserting a synthetic event then a synthetic alert succeeds; `storage_policy` shows hot→cold volumes; a row past the hot TTL **moves to the cold volume** (verified via `system.parts` `disk_name`); ReplicatedMergeTree config present. Publish DDL in CONTEXT.md. |
| **DATABASE-4** | **Inverted-index log search over ClickHouse.** Add **inverted (full-text) indices** on event/alert payload text columns, plus **bloom/token/ngram + min-max skip indices** for fast investigative search. Tokenized-search query helpers for the investigation API (search by employee, IP, beneficiary, free text). | `db/clickhouse/indexes.sql`, `db/clickhouse/search_helpers.sql` | REAL | Part 8 (inverted indices for log search; "Search → ClickHouse inverted indices", l.305–306, 318) | Indices create (`INDEX … TYPE inverted`/`ngrambf_v1`/`tokenbf_v1`/`minmax`, with `SET allow_experimental_inverted_index=1` where required); a full-text query over a payload text column returns the seeded match; `EXPLAIN`/`system.parts` shows index granules pruned (skip-index effective); helper functions return correct results for the documented investigative queries. |

### M3 — Immutable WORM audit trail
*A tamper-evident, append-only, regulator-grade audit trail of all system and investigator activity, sealed to WORM object-lock storage.*

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **DATABASE-5** | **Append-only Kafka audit topics.** Topic config: **compaction OFF, retention = infinite (append-only)**; producer **schema for audit events** (who-viewed-whom, alert closes, disposition writes, rule/threshold changes, model-version changes, feature-snapshot writes, **PII unmask**, narrative audit memos). 3-partition / RF-aware config consistent with DATA's cluster. | `infra/audit/kafka/topics.yaml`, `infra/audit/kafka/audit_event.avsc`, `infra/audit/create_topics.sh` | REAL | Part 8 (append-only Kafka audit topics + WORM, l.311); Part 19.3 (tamper-evident audit of all activity incl. investigators, l.634) | The `audit-events` topic is created with `cleanup.policy=delete`, `retention.ms=-1` (infinite), compaction off; the producer schema validates a sample of **each** audit event type (incl. who-viewed-whom + rule-change + unmask + narrative-memo); a produced record is consumable in order. Schema published in CONTEXT.md. |
| **DATABASE-6** | **WORM object-lock store + tamper-evident audit log.** A writer/sink that drains the Kafka audit topic into **object-lock (immutable, compliance-mode-equivalent) buckets** with **per-record hash-chaining (each record carries prev-hash) + periodic Merkle root anchoring** (e.g., daily root persisted/printed). Covers **alerts, dispositions, model versions, feature snapshots, rule/threshold changes, and investigators' own actions**. Plus a **verification CLI** that re-walks the chain + recomputes the Merkle root and reports any tampering. | `services/audit/worm_writer.py`, `services/audit/hashchain.py`, `services/audit/verify_cli.py` | REAL | Part 9.3 (WORM for alerts/dispositions/model versions/feature snapshots, l.364); Part 19.3 (append-only/WORM incl. investigators' actions; watch-the-watchers, l.634); Part 8 (WORM storage, l.311); Part 19.2 (registry access logging is one of the audited streams, l.626) | Producing N audit events seals N immutable objects to the object-lock bucket (a delete/overwrite within retention is **rejected** by object-lock); each record's `prev_hash` chains to the prior; the verify CLI returns **PASS** on an untouched chain and **FAIL** with the offending record when a stored object's bytes are tampered (test by mutating a copy); the daily Merkle root is reproducible. Covers all six record classes above. |

### M4 — Model-file registry & artifact security
*The versioned, signed, encrypted, object-locked model registry storing every layer's artifacts with full reproducibility metadata and theft mitigations.*

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **DATABASE-7** | **Model file-format & transform-chain artifact layout.** A spec + serializer utils persisting the **whole transform chain together**: trees → **ONNX + native** (`.txt`/`.cbm`/joblib); nets (L4/L5) → **ONNX + PyTorch checkpoint**; **preprocessors/feature transformers/calibrators versioned with the model**. Object-store path layout `{bucket=models}/{layer}/{model}/{version}/` (e.g. `models/L3/lightgbm_gbdt/v1.4.2/`) holding `model.onnx`, native booster, `transform_chain/`, `calibrator.joblib`, `metadata.json`, `signature.sig`. | `registry/artifacts/layout.md`, `registry/artifacts/serializer.py` | REAL | Part 23.1 (formats, l.855–858); Part 23.2 (layout `{layer}/{model}/{version}/`, l.861) | The serializer round-trips a synthetic tree artifact (ONNX + native + calibrator + preprocessor) into the exact path layout and reloads the **whole chain**; a net artifact round-trips (ONNX + PyTorch checkpoint); `metadata.json` carries all required fields (see DATABASE-8); layout matches the blueprint path exactly. Publish layout in CONTEXT.md so ML packages into it. |
| **DATABASE-8** | **MLflow registry with signing, encryption & access logging.** Config + helpers for **Staging→Production→Archived** stages; artifacts in **versioned, encrypted-at-rest, object-lock** buckets; **each version records dataset hash, params, metrics, training-code commit, approver, cryptographic signature**; **model signing with signature verified on load**; **registry access logging** (every read/promote/load → an audit event onto the audit topic, for extraction-theft mitigation). Owns the **storage/layout/signing/verify/access-log** side; the MLflow *tracking server runtime* is ML/PLATFORM. | `registry/mlflow/config.py`, `registry/mlflow/signing.py`, `registry/mlflow/access_log.py`, `registry/mlflow/load_verify.py` | REAL | Part 23.2 (registry stages + per-version metadata, l.860–862); Part 23.3 (encrypted-at-rest, object-lock, least-privilege, signing verified on load, lifecycle, l.864–865); Part 23.4 (serving pulls Production + verifies signature, l.867–868); Part 19.2 (encrypted+signed+access-controlled+access-logged registry, l.626) | Registering a synthetic model writes a version with **all six** metadata fields (dataset hash/params/metrics/code-commit/approver/signature) and a detached signature; a Staging→Production promotion is recorded; **load with a valid signature succeeds, load with a tampered artifact/signature is REJECTED**; every registry read/promote/load emits an access-log audit event onto the audit topic (verifiable via DATABASE-6); buckets are encrypted + object-locked + least-privilege. |

### M5 — Retention & archival tiering
*DPDP/RBI-aligned lifecycle that ages data hot ClickHouse → cold object store → archive across all stores.*

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **DATABASE-9** | **Retention & archival tiering hot→cold→archive.** Policies + a scheduled job: ClickHouse **TTL-MOVE** to cold object store then to an **archive tier**; **object-store lifecycle rules** (transition + expiration honoring object-lock); **audit-log archival** (WORM objects age to archive but remain immutable/verifiable); **retention windows parameterized to DPDP retention + RBI record-keeping**, with **data-classification-driven** retention (PII/PAN/sensitive vs operational, per Part 28.2) and **fraud carve-outs** (longer hold for confirmed-fraud cases/audit). | `db/retention/policies.yaml`, `db/retention/retention_job.py`, `db/retention/clickhouse_ttl.sql` | REAL | Part 28.2 (tiered hot→cold→archive, DPDP/RBI; classification drives retention, l.1208, 1203); Part 9.3 (data minimization + retention limits aligned to RBI, l.363); Part 23.3 (lifecycle archives old model versions, l.865) | `policies.yaml` declares per-store windows keyed to DPDP/RBI with a documented rationale + fraud carve-out; running the job moves an aged ClickHouse partition hot→cold→archive and applies object-store lifecycle transitions; **object-lock/WORM retention is never shortened below its lock period** (job refuses to expire locked objects early); old model versions archive per lifecycle; retention windows are classification-aware (PII vs operational). Publish windows in CONTEXT.md. |

**Inventory-JSON ↔ task mapping (all 11 components covered):**
- "Immutable tamper-evident audit trail; reproducibility; model-governance evidence" → DATABASE-6 (+ DATABASE-2 governance schemas, DATABASE-8 reproducibility metadata).
- "ClickHouse columnar analytics store with hot-cold tiering and inverted indices" → DATABASE-3 + DATABASE-4.
- "Search via ClickHouse inverted indices" → DATABASE-4.
- "Append-only Kafka audit topics + WORM/object-lock storage" → DATABASE-5 + DATABASE-6.
- "Append-only/WORM storage for alerts, dispositions, model versions, feature snapshots" → DATABASE-6 (record classes) + DATABASE-1 (object-lock buckets).
- "Model file formats: trees→ONNX+native; nets→ONNX+checkpoint; preprocessors/calibrators versioned together" → DATABASE-7.
- "MLflow Model Registry Staging→Production→Archived + per-version metadata + signature" → DATABASE-8.
- "Storage security: encrypted at rest, versioned+object-lock, least-privilege RBAC, signing verified on load, lifecycle archival" → DATABASE-1 + DATABASE-8 + DATABASE-9.
- "Model extraction/theft mitigations: encrypted signed artifacts, access-controlled registry, registry access logging" → DATABASE-8.
- "Append-only/WORM tamper-evident audit of all activity incl. investigators' actions" → DATABASE-6 (+ DATABASE-5 event types).
- "Retention & archival tiering aligned to DPDP/RBI" → DATABASE-9.

**Must-cover capability ↔ task mapping (all covered):** ClickHouse cluster schema events/scores/features-history + hot-cold + inverted search → DATABASE-3/4; Postgres cases/users/alerts metadata → DATABASE-2; Redis online-feature config → DATABASE-2; MinIO/S3 object store (models+datasets, partitioned Parquet, SSE/versioned/object-lock) → DATABASE-1 (+ partitioned-Parquet dataset layout note, see §7); WORM/append-only immutable audit → DATABASE-5/6; retention/archival tiering DPDP/RBI → DATABASE-9; model-file registry layout with dataset hash/metrics/approver/signature → DATABASE-7/8; encryption-at-rest config → DATABASE-1/2 (+ KMS/HSM swap note); DDL versioning/migrations → DATABASE-2 (Alembic) + ClickHouse DDL versioning convention (see §7).

---

## 7. Detailed build instructions per milestone

These spell out the blueprint specifics so nothing is lost. Follow them precisely.

### M1 — Object store, Postgres, Redis, encryption

**DATABASE-1 — MinIO object store.**
- Buckets (create exactly): `models`, `datasets`, `feature-snapshots`, `audit-archive`.
- Enable **versioning** on all four; enable **object-lock** on `models` and `audit-archive` (immutability for artifacts + WORM audit). Object-lock requires the bucket be created with lock enabled — do this at creation.
- **Encryption-at-rest:** configure MinIO SSE (SSE-S3 with the auto-encryption policy, or SSE-C with a local key). Document the **1:1 swap to S3 SSE-KMS** for AWS. The key lives locally for dev (PLATFORM owns the real key custody seam — note it).
- **Least-privilege RBAC:** define MinIO policies — `models-writer` (ML packaging), `models-reader` (serving load), `datasets-rw` (DATA), `audit-writer` (WORM writer, write+lock only, no delete), `read-only-auditor`. No principal gets `*`.
- **Partitioned-Parquet dataset layout** (Part 21.5): document and enforce the `datasets/{dataset_name}/dt={YYYY-MM-DD}/source={src}/part-*.parquet` partition convention (by **date/source**) for raw events + curated sets; DVC remote points at the `datasets` bucket; each curated set carries a **content hash** in a sidecar.
- Provide a Terraform **module stub** (`plan`-only) mirroring the compose, so PLATFORM can apply the AWS S3 (SSE-KMS + object-lock) equivalent later.

**DATABASE-2 — Postgres + Redis.**
- **Postgres schemas / core tables** (via Alembic, one migration per logical unit, reversible):
  - `users` (user_id, keycloak_subject, role, status, created_ts) — RBAC roles per Part 24.1 (Analyst, Senior Investigator, Team Lead/MLRO, Compliance, Auditor, Model Engineer, Platform Admin, Service account). You store the rows; BACKEND enforces.
  - `cases` (case_id, status, assignee, created_ts, linked_alert_ids[], notes ref) + `case_notes`, `case_history`.
  - `alerts_metadata` (alert_id, entity_id, status, severity, sla_due_ts, assignee) — the relational mirror of the ClickHouse `alerts` rows for case workflow joins (full alert body lives in ClickHouse).
  - `model_governance` (model, version, owner, purpose, risk_tier, model_card_uri, validation_report_uri) + `approvals` (approval_id, model_version, approver, decision, ts) — four-eyes / sign-off records ML/BACKEND write.
  - **Re-id vault table instance** (`pii_vault`: token, ciphertext, created_ts) — you create the encrypted-at-rest table + RBAC; **BACKEND owns the write path + HMAC key (seam); store only tokenized/ciphertext, never real PII.**
- **DDL versioning:** Alembic is the system of record; `alembic upgrade head` / `downgrade` must be clean and reversible; tag each migration with the DATABASE task + blueprint Part in its docstring.
- **Least-privilege Postgres roles:** `hawkeye_app` (DML), `hawkeye_ro` (SELECT, for auditor/read paths), `hawkeye_migrate` (DDL). App never runs as superuser.
- **Redis:** DB0 = Feast online serving, DB1 = cache (publish keyspace convention in CONTEXT.md). Configure **at-rest** (RDB/AOF on an encrypted volume; note the swap to a KMS-backed volume), `requirepass`, and a maxmemory + eviction policy suitable for online features. You provide the instance + config; **DATA defines the feature keys, ML/BACKEND read** (seam).

### M2 — ClickHouse

**DATABASE-3 — tables + hot-cold tiering.**
- `events` table mirrors **BACKEND.md §1** exactly: flatten Actor/Action/Object/Context plus a `linkage` map (correlation keys: SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account). `PARTITION BY toYYYYMM(ts)`, `ORDER BY (actor_employee_id, ts)`, `event_id` for idempotency. Engine **ReplicatedMergeTree** (cluster-ready) with the cluster macros; keep a `MergeTree` fallback for single-node local dev (toggle via a config var).
- `scores` (event_id/alert ref, layer enum L1..L6, raw_score, calibrated_score, model_version, ts) — per-layer + fused history; `model_version` recorded on **every** score (Part 23.4 / BACKEND.md §6).
- `alerts` mirrors **BACKEND.md §2** (alert_id, entity_id, risk_score, severity, confidence, status, created_ts, contributing_layers[], reason_codes nested, exposure_inr, sla_due_ts, pii_tokenized).
- `dispositions` mirrors **BACKEND.md §5** (alert_id, outcome, notes, evidence_ids[], label_written, audit_id, ts) — the EDD outcome → **label** rows ML's feedback loop reads.
- `feature_backfill` — the **offline** feature table with **identical definitions to the online Feast/Redis features** (DATA owns the defs; you provide the skew-free offline store target per Part 21.5).
- **Hot-cold tiering** (`storage_configuration.xml`): define a `default` (hot, SSD) disk + a `cold` (S3/MinIO-backed) disk + a `s3_archive` disk; a `tiered` **storage policy** with `volumes: hot → cold`; on each table add `TTL ts + INTERVAL 30 DAY TO VOLUME 'cold'` (hot window ~14–30 days, parameterized). Expect ~10–20× compression (Part 9.2) — use appropriate codecs (`CODEC(ZSTD)`, `Delta`/`DoubleDelta` for timestamps).
- **Cluster:** ship a `cluster.xml` with a small sharded+replicated topology (Part 9.2) + ZooKeeper/Keeper macros; document scaling by shard.

**DATABASE-4 — inverted-index search.**
- Add **inverted (full-text)** indices on free-text/payload columns (`INDEX … TYPE inverted` / `gin`-style, enabling the experimental flag where the CH version requires it) for log search (Part 8 "Search → ClickHouse inverted indices").
- Add **token/ngram bloom** (`tokenbf_v1`, `ngrambf_v1`) and **min-max** skip indices on high-cardinality investigative columns (employee_id, ip, beneficiary_id, device, session_id) for fast pruning.
- Provide `search_helpers.sql` with parameterized investigative queries: search by employee, by IP/device, by beneficiary, and free-text over reason_codes/notes — the queries the investigation API (BACKEND) will call.

### M3 — WORM audit

**DATABASE-5 — audit topics.**
- `audit-events` topic: `cleanup.policy=delete`, `retention.ms=-1` (infinite), **compaction off**, partitions consistent with DATA's cluster (3+), RF per cluster.
- Producer **schema** (`audit_event.avsc`) — one event envelope with `audit_id` (`aud_*`), `ts`, `actor` (who), `action` enum, `target` (entity/alert/rule/model/feature ref), `details`, `prev_hash` placeholder (filled by the WORM writer). Action enum must cover: **who-viewed-whom**, alert assign/close/disposition, **rule/threshold change**, model-version change/promote, **registry access (read/load)**, feature-snapshot write, **PII unmask**, and **narrative audit memo** (provider, tee_attested, attestation_id, model, prompt_hash — BACKEND.md §7).
- BACKEND emits these (seam); you own the topic + schema contract. Publish in CONTEXT.md.

**DATABASE-6 — WORM writer + hash-chain + verify.**
- `worm_writer.py`: consume `audit-events` in order; for each record compute `record_hash = H(canonical_bytes ‖ prev_hash)`; write the sealed record to the `audit-archive` object-lock bucket (immutable; retention period set on the object); persist a running chain head.
- `hashchain.py`: the chaining + **Merkle anchoring** (build a daily Merkle tree over the day's records, persist/print the **daily root**; the root is the tamper-evidence anchor a regulator can pin).
- `verify_cli.py`: re-read sealed objects, recompute the chain + daily Merkle root, and report **PASS/FAIL** with the first divergent record on tamper. Test by mutating a *copy* (the real object-lock object cannot be mutated — that itself is the immutability proof).
- Coverage: alerts, dispositions, model versions, feature snapshots, rule/threshold changes, **investigators' own actions** (watch-the-watchers, Part 19.3), and registry access (Part 19.2).

### M4 — Model registry

**DATABASE-7 — artifact layout.**
- Path layout (exact): `models/{layer}/{model}/{version}/` containing `model.onnx`, native booster (`booster.txt` / `model.cbm` / `model.joblib`), `transform_chain/` (preprocessors/transformers), `calibrator.joblib`, `metadata.json`, `signature.sig`. For nets: `model.onnx` + `checkpoint.pt`.
- `serializer.py`: `save_chain(...)` and `load_chain(...)` that persist/reload the **whole transform chain together** (a model is never just the estimator — Part 23.1). Round-trip must reconstruct identical predictions on a fixture vector.

**DATABASE-8 — MLflow registry storage/signing/access-log/verify.**
- Stages **Staging→Production→Archived**; artifacts in the encrypted + object-locked `models` bucket at the DATABASE-7 layout.
- `metadata.json` per version records **all six**: `dataset_hash`, `params`, `metrics`, `training_code_commit`, `approver`, `signature`. (Lineage dataset_hash + feature-set version ties to Part 21.5.)
- `signing.py`: detached signature over the artifact bundle (cosign/sigstore or `cryptography` Ed25519 with a local key). `load_verify.py`: **verify signature on load; reject on mismatch/tamper** (Part 23.3/23.4 + 19.4).
- `access_log.py`: every registry read/promote/load emits an **access-log audit event** onto the audit topic (DATABASE-5/6) — the extraction-theft mitigation (Part 19.2). Least-privilege bucket policies from DATABASE-1.
- **Seam:** the MLflow *tracking server runtime* is ML/PLATFORM; you provide the **storage backend config, layout, signing, verify-on-load, and access logging**. Publish the path + signature contract in CONTEXT.md so ML packages into it and BACKEND's serving loader verifies against it.

### M5 — Retention

**DATABASE-9 — retention/archival tiering.**
- `policies.yaml`: per-store retention windows keyed to **DPDP retention + RBI record-keeping**, with a documented rationale per class and a **fraud carve-out** (confirmed-fraud cases + their audit/evidence held longer). Classification-aware (PII/PAN/sensitive vs operational, Part 28.2).
- `clickhouse_ttl.sql`: TTL-MOVE hot→cold then to `s3_archive`; old partitions ultimately archive.
- `retention_job.py`: scheduled job applying ClickHouse moves, MinIO **lifecycle rules** (transition + expiration), audit-log archival (WORM objects age to archive but remain immutable + verifiable), and old-model-version archival (Part 23.3). **Never expire/shorten an object-lock object below its lock period** — the job must refuse and log.

---

## 8. Testing & all checks (commands + what must pass)

Run from the repo root unless noted. All commands must pass before a milestone is Done.

**Project setup / dependency pinning:**
- Pin every dependency to the **Part 24.3** versions (ClickHouse 25.x, Postgres 17.x, Redis 7.4.x, MLflow 2.18, Python 3.12.x, Docker 27, Terraform 1.9, MinIO latest stable). Freeze in `db/requirements.txt` (Python tooling) + `db/README.md` + your compose image tags. **No floating `latest` tags except MinIO** (pin its release date/tag too).

**Lint / format / type (Python tooling under `db/`, `registry/`, `services/audit/`):**
```
ruff check db registry services/audit
black --check db registry services/audit
mypy db registry services/audit
```
**SQL lint:**
```
sqlfluff lint db/clickhouse db/postgres   # dialect: clickhouse / postgres
```

**Unit tests (your own, under `db/tests/` or `tests/database/` — you own these):**
```
pytest db/tests -q
```
Must cover: Alembic upgrade/downgrade reversibility; ClickHouse DDL applies + L0/L6 column-parity assertions; storage-policy + TTL-MOVE moves a part to the cold disk; inverted/skip-index queries return correct rows; WORM hash-chain verify PASS on clean + FAIL on tampered copy + Merkle-root reproducibility; registry serializer chain round-trip; signature verify-on-load accept/reject; registry access emits an audit event; retention job moves partitions + refuses to break object-lock.

**Integration tests (local stack):**
```
docker compose -f infra/storage/docker-compose.storage.yml up -d
pytest db/tests/integration -q
```
Must cover the cross-store flows: insert event → score → alert → disposition into ClickHouse; produce an audit event → WORM seal → verify; package a synthetic model → register → promote Staging→Production → load-with-verify; retention move across hot→cold→archive. Contribute these fixtures to **PLATFORM's** cross-workstream integration harness (they own the harness; you contribute).

**Contract tests:**
- Assert your ClickHouse `events`/`alerts`/`dispositions` columns **match `BACKEND.md` §1/§2/§5** field-for-field; fail the test if BACKEND.md changes and your DDL drifts (so the seam stays honest).
- Assert the audit-event schema validates a sample of **every** action type.
- Assert the registry layout/path + `metadata.json` six-field shape matches the contract you published in CONTEXT.md.

**Security scans (your dirs):**
```
trivy fs db registry services/audit infra/storage infra/audit   # CVE + secret scan
```
Plus: confirm **no real PII / no real creds** anywhere (synthetic only); confirm object-lock + SSE are ON in config; confirm least-privilege policies deny over-broad access; confirm signature-verify-on-load rejects tampered artifacts.

**Performance / budget checks (where relevant):**
- ClickHouse investigative search (DATABASE-4) over a seeded ~1M-row synthetic set returns **sub-second** for the entity-360 / search helper queries (Part 8 "sub-second queries"); record the timing in your log.
- WORM writer keeps up with the audit topic without unbounded lag on the synthetic burst.

**Definition of Done per milestone (all must hold):**
- M1: MinIO (4 buckets, versioned, object-lock on models+audit-archive, SSE, least-privilege) + Postgres (schemas via reversible Alembic, least-privilege roles) + Redis (encrypted, keyspace) all up via compose; contracts published in CONTEXT.md.
- M2: ClickHouse 5 tables mirror L0/L6; hot-cold TTL-MOVE proven; inverted + skip indices + search helpers work sub-second; cluster config present.
- M3: append-only infinite-retention audit topic + full action schema; WORM writer seals immutably with hash-chain + daily Merkle root; verify CLI PASS/FAIL works; all six record classes + investigator actions covered.
- M4: registry layout round-trips the whole transform chain; Staging→Production→Archived; six-field metadata + signature; verify-on-load accept/reject; registry access logged.
- M5: DPDP/RBI-keyed retention windows + fraud carve-out; job moves hot→cold→archive across stores; object-lock never broken early.
- Every milestone: lint/format/type/sqlfluff/unit/integration/contract/security all green; TODO.md + CONTEXT.md + your laptop log updated.

---

## 9. Blueprint validation gate (each owned requirement → covered)

A task is "done" only when its blueprint requirement is met. Tick each in your laptop log with the Part + line cite.

| Blueprint requirement (Part · ~line) | Covered by | Validation evidence required |
|---|---|---|
| ClickHouse as analytical/investigation store (Part 8 · l.305) | DATABASE-3 | 5 tables up, L0/L6 parity, sub-second queries |
| Hot-cold tiering (Part 8 · l.305, 318; Part 9.2 · l.357) | DATABASE-3, DATABASE-9 | TTL-MOVE moves part hot→cold→archive |
| Inverted indices for log search (Part 8 · l.305–306) | DATABASE-4 | full-text + skip-index queries return correct rows |
| Sharded+replicated cluster + compression (Part 9.2 · l.357) | DATABASE-3 | ReplicatedMergeTree + cluster.xml + ZSTD codecs |
| Redis online feature store sizing (Part 8 l.301; 9.2 l.359) | DATABASE-2 | Redis up, DB0/DB1 keyspace, maxmemory policy |
| Append-only / WORM for alerts, dispositions, model versions, feature snapshots (Part 9.3 · l.364) | DATABASE-6 | all four classes sealed immutably + verifiable |
| Field-level encryption / at-rest; HSM-for-keys swap (Part 9.3 · l.363) | DATABASE-1/2 + KMS/HSM seam note | SSE on; KMS/HSM swap documented |
| Append-only Kafka audit topics + WORM (Part 8 · l.311) | DATABASE-5/6 | infinite-retention topic + WORM sink |
| Tamper-evident audit of ALL activity incl. investigators (Part 19.3 · l.634) | DATABASE-6 | who-viewed-whom + rule-change + unmask sealed |
| Model extraction/theft: encrypted+signed+access-controlled+access-logged registry (Part 19.2 · l.626) | DATABASE-8 | signed at rest, least-priv, every access logged |
| Model formats: trees ONNX+native; nets ONNX+checkpoint; transform chain versioned together (Part 23.1 · l.855–858) | DATABASE-7 | whole-chain round-trip |
| MLflow registry Staging→Production→Archived + per-version dataset hash/params/metrics/commit/approver/signature (Part 23.2 · l.860–862) | DATABASE-8 | version has all six fields + stage transition |
| Encrypted-at-rest + object-lock + least-privilege + sign-verified-on-load + lifecycle (Part 23.3 · l.864–865) | DATABASE-1/8/9 | verify-on-load reject; object-lock on; lifecycle |
| Serving pulls Production + verifies signature; model version per score (Part 23.4 · l.867–868) | DATABASE-8 (+ ClickHouse `scores.model_version`) | load-verify helper + model_version column |
| Dataset storage: ClickHouse + partitioned Parquet object store; DVC/MLflow + content hash; Feast offline; dataset-hash+feature-set-version lineage (Part 21.5 · l.823–826) | DATABASE-1 (Parquet layout + DVC) + DATABASE-3 (`feature_backfill`) + DATABASE-8 (lineage hash) | partition layout + content hash + lineage fields |
| Retention & archival tiering hot→cold→archive aligned to DPDP/RBI (Part 28.2 · l.1208) | DATABASE-9 | windows keyed to DPDP/RBI + fraud carve-out |
| Classification drives masking/access/retention (Part 28.2 · l.1203) | DATABASE-9 (+ DATABASE-1/2 RBAC) | classification-aware retention classes |
| DDL versioning / migrations | DATABASE-2 (Alembic) + ClickHouse DDL version convention | reversible migrations; versioned DDL |

If any row cannot be ticked, mark the TODO row `[!]` and raise it in CONTEXT.md.

---

## 10. Definition of Done & handoff

**You are done when all of the following hold:**
1. All 9 tasks (DATABASE-1..9) meet their acceptance checks and every blueprint-validation-gate row (§9) is ticked in your laptop log with a Part + line cite.
2. All checks in §8 pass (lint/format/type/sqlfluff, unit, integration, contract, security; sub-second search budget recorded).
3. `docker compose -f infra/storage/docker-compose.storage.yml up` brings MinIO + Postgres + Redis + ClickHouse online locally; migrations apply; the WORM writer and verify CLI run; the registry round-trips a synthetic model with signature verify; the retention job runs.
4. **MD files updated:**
   - **`CONTEXT.md`** — integration-log entries (newest first) for: ClickHouse table DDLs + partition/TTL, MinIO bucket/path conventions + registry layout `{layer}/{model}/{version}/`, Redis keyspace + encryption, WORM audit event schema + verify CLI usage, retention windows + DPDP/RBI rationale, encryption-at-rest approach + KMS/HSM swap, and any deviations (with Part cited).
   - **`TODO.md`** — section 5 (DATABASE) all rows `[x]` (or `[!]` with a CONTEXT.md note); §7 cleared of your blockers.
   - **`docs/laptops/05-database.md`** — full log: decisions, files created, blueprint validations (Part+line), deviations + rationale, blockers + resolutions, AWS↔on-prem swap notes, performance numbers.
   - **`BACKEND.md`** — you do NOT edit it; if you needed a contract change you proposed it in CONTEXT.md tagging BACKEND.
5. **Git:** all work on `hawk-eye/database`; commits use `[DATABASE] <TASK-ID> <msg> (blueprint Part X)`; only owned dirs + your log touched + append-only shared MD; merges to `main` clean because ownership is disjoint.

**Integration handoff (prove the seams, then notify the consumers in CONTEXT.md):**
- **DATA** — confirm your `events` + `feature_backfill` tables match the L0 schema/feature defs (reconcile when DATA finalizes the `.avsc`/`.proto`).
- **ML** — confirm they package model artifacts into your `{layer}/{model}/{version}/` layout, your six-field metadata, and that their MLflow tracking integrates with your storage/signing/access-log config; confirm dataset-hash + feature-set-version lineage flows.
- **BACKEND** — confirm their audit-event producer matches your `audit_event.avsc`; confirm their investigation API queries hit your ClickHouse tables + search helpers; confirm their serving loader uses your signature-verify-on-load; confirm `scores.model_version` is recorded per score; confirm the re-id vault table instance + RBAC meet their tokenization write path.
- **FRONTEND** — confirm the auditor/timeline views read your ClickHouse audit + event tables (via BACKEND).
- **PLATFORM** — hand your `infra/storage/` + `infra/audit/` Terraform stubs to be included in the global stack; confirm KMS/HSM key-custody + Vault seam; contribute your integration fixtures to their cross-workstream harness + CI.

Run the end-to-end smoke (synthetic event → score → alert → disposition → audit-WORM-seal → registry register/promote/verify-load → retention move) and record PASS in your laptop log before declaring Done.
