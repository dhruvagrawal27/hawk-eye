# Hawk-Eye — Laptop 01: DATA — Claude Code Build Prompt

> **You are the DATA laptop.** You own the data backbone of the Hawk-Eye insider/privileged-user fraud-detection platform: the **L0 unified event model**, the **Kafka/Flink/Feast+Redis/ClickHouse** streaming-and-feature substrate, a fully **synthetic agent-based simulator** that emits labelled insider-fraud telemetry, **scaffolded source connectors** (CBS/SWIFT/IAM/PAM/DB-audit/HR), the **full feature-engineering catalogue** feeding L2–L5, **dataset & label sourcing** (public benchmarks + weak/synthetic/EDD labels), and **data governance / quality / lineage / MDM**. You are Workstream 1 of 6. Build on branch `hawk-eye/data`, owning the `data/` directory (plus your own log file and append-only edits to the shared MD files). This document is self-contained and authoritative for your workstream — read it fully, then build top to bottom.

---

## 0. Mission & golden rules

**Mission.** Deliver every downstream layer (BACKEND L1 rules, ML L2–L6, DATABASE storage, FRONTEND timeline) one normalized, governed, labelled event stream and one feature surface, all running locally on **synthetic + public** data with **zero live-bank dependency**. When a real bank feed or real fraud-label source is required, you ship the connector/code as **SCAFFOLD** (correct code that goes live only when a real resource is plugged in) or **MOCK** (a seeded stand-in for a human/legal act). Everything that can run for real on synthetic/public data must be **REAL**.

**The five golden rules — restate them at the top of every session and never violate them:**
1. **ALERT-ONLY.** The platform scores and explains; a human decides; **it never auto-blocks money or a transaction.** Nothing you build may take an enforcement action. Your simulator may *label* fraud, but it never *blocks* anything.
2. **ON-PREM + SYNTHETIC ONLY.** No real PII, no real bank feeds, no cloud creds, no real credentials, no production SWIFT/CBS/PAM endpoints. Everything runs locally against the synthetic simulator and public benchmark datasets. Real feeds/creds/hardware → **SCAFFOLD**; human/legal/hardware acts → **MOCK**.
3. **VALIDATE AGAINST THE BLUEPRINT.** No task is "done" until the matching blueprint Part's requirement is demonstrably met. Cite the Part in every commit and in your laptop log. The blueprint (`Insider_Fraud_Detection_Implementation_Blueprint (2).md`) is the authoritative spec.
4. **NOTHING DROPPED.** Your task list below partitions the entire DATA portion of the blueprint. If you discover a DATA requirement not represented here or in any other laptop's list, raise it in `CONTEXT.md` immediately and tag the owning laptop.
5. **STAY IN YOUR LANE.** Edit only files **under `data/`**, your own log `docs/laptops/01-data.md`, and **append-only** to `CONTEXT.md` / `TODO.md`. Never edit another laptop's directory or `BACKEND.md` (that is BACKEND-owned; you READ it).

**Status legend (use it on every task and in every commit/log):**
- **REAL** — works as real code on synthetic/mock/public data, locally.
- **SCAFFOLD** — code complete and correct, needs a real external resource (live bank feed, cloud creds, API key, HSM/TEE, human validator) to go live.
- **MOCK** — hardcoded/simulated stand-in for a human/legal/hardware act (seeded records, generated docs, fake attestation).

---

## 1. Mandatory reading before any code

**Do this at the start of EVERY session, in this order. Do not write code until you have done it.**

1. **The blueprint — your primary Parts, read in full:**
   - **Part 5 — Data strategy** (~l.160–210): 5.1 unified event model (Actor/Action/Object/Context/Linkage), 5.2 feeds, 5.3 public datasets, 5.4 the four label sources, 5.5 synthetic data (agent-based + generative caveats + imbalance handling).
   - **Part 6 — Feature-engineering catalogue** (~l.212–261): the three-way baseline framework + 6.1 identity/access, 6.2 transaction, 6.3 data-layer, 6.4 change/HR, 6.5 graph, 6.6 temporal, plus the streaming/Feast/ClickHouse/featuretools engineering note.
   - **Part 21 — How we create the dataset** (~l.787–828): 21.1 agent-based simulator (population, normal-behaviour, fraud injectors per typology, ground-truth labels, scale knobs), 21.2 generative augmentation, 21.3 real telemetry & labelling (PU/semi-supervised), 21.4 splits & leakage avoidance, 21.5 storage & versioning.
   - **Part 32 — Integration architecture & source onboarding** (~l.1287–1309): 32.1 ingestion adapters per source + SWIFT↔CBS recon + CDC/batch pattern + schema governance, 32.2 reliability patterns + count reconciliation, 32.3 source-onboarding playbook.
   - **Part 28.2 — Data management foundations** (~l.1201–1208): catalog/dictionary, classification, quality, lineage, schema registry & evolution, MDM, retention/archival. Also **28.1** (~l.1193–1199) for data minimization / purpose limitation / retention & erasure with fraud carve-outs.
2. **The blueprint — skim for seams you consume/produce:** Part 0 (executive summary, L0/L1 mention), Part 8 (tech stack), Part 18.1 (online path: per-entity baseline/peer-stat caching in Redis with TTLs — l.592), Part 24.3 (pinned versions — l.917–943), Part 24.5(a)/(d) (sample event + worked burst — l.963–1025), Part 31.1 (data validation tests — l.1261).
3. **`BUILD_PLAN.md` → "📥 DATA — Workstream"** (l.38–110): your 28 tasks, 5 milestones, dependencies, and the cross-workstream dependency list.
4. **The three shared MD files (read every session):**
   - **`CONTEXT.md`** — shared brain + integration log. Read it fully; check the log for decisions others made that affect you.
   - **`BACKEND.md`** — the integration contract (L0 event JSON, L6 alert JSON, API routes, RBAC, versions). **You READ this; you do not edit it.** Your L0 schema MUST match §1 of `BACKEND.md`.
   - **`TODO.md`** — the shared board; keep your DATA rows current.
5. **`README.md`** — golden rules, repo layout, merge model.

---

## 2. The MD-file coordination protocol (the four files, exact read/write rules)

There are **four kinds** of coordination files. Obey these rules exactly.

### 2.1 `CONTEXT.md` — shared full context (everyone appends; newest first)
- **READ** it at the start of every session — especially the **INTEGRATION LOG** at the bottom.
- **APPEND** (never overwrite, never delete others' entries) whenever you make a **cross-cutting decision** that affects another laptop: a schema field, a feature name/key, a topic name, a Parquet layout, a port you rely on, a convention, or a deviation from the blueprint. Add to the **top** of the integration log using the format:
  ```
  ### YYYY-MM-DD — [DATA] — <short title>
  <one or two sentences: what changed, who it affects, why>
  ```
- Examples you WILL append: "L0 Avro schema finalized + registry compatibility = BACKWARD"; "feature key naming convention `<entity>:<feature>:<window>`"; "simulator emits to Kafka topic `events.raw` and Parquet under `data/out/<date>/`"; "SWIFT↔CBS recon emits signal `recon_mismatch` on topic `events.signals`".
- If you need a change to a **contract** owned by BACKEND (L0/L6 JSON shape, IDs), **propose it in `CONTEXT.md` and tag `[BACKEND]`** — do not edit `BACKEND.md` yourself.

### 2.2 `BACKEND.md` — the integration contract (BACKEND owns; you READ)
- **Owner: the BACKEND laptop.** Everyone else integrates against it and **must not edit it**.
- You consume from it: the **L0 unified event JSON** (§1 — *DATA owns the schema, BACKEND consumes*), the **L6 alert JSON** (§2 — so your EDD-feedback label-source-4 ingestion matches), the **pinned versions** (§0), the **IDs convention** (event_id `evt_*`, entity_id = employee_id `EMP-*`, ring_id `RNG-*`), and the **disposition/feedback** contract (§5, the source of your label-source-4).
- **Critical seam:** `BACKEND.md` §1 says "**DATA owns the schema, BACKEND consumes**." So **you are the authority on the L0 event schema's fields**, but the canonical JSON example lives in `BACKEND.md`. Keep your `schemas/l0_event.py` / `.avsc` / `.proto` **byte-for-byte field-compatible** with `BACKEND.md` §1. If you must add/rename a field, propose it in `CONTEXT.md` tagged `[BACKEND]` and wait for BACKEND to mirror it.

### 2.3 `TODO.md` — shared task board (keep your rows current)
- Update the **"📥 DATA"** section. Use `[ ]` todo, `[~]` in-progress, `[x]` done (only when blueprint-validated), `[!]` blocked.
- Put cross-laptop blockers in **§7** of `TODO.md`, tag the owning laptop, and mirror the blocker in `CONTEXT.md`.

### 2.4 `docs/laptops/01-data.md` — YOUR OWN log file (you own and maintain it)
- This is your working journal. Update it **every session**. It MUST contain, kept current:
  - **Decisions** (and why), with the blueprint Part cited.
  - **Files created/changed** (path + one-line purpose).
  - **Blueprint validations** — for each task, the Part ref and the acceptance check you ran to call it done.
  - **Deviations** from the blueprint (with justification) and **assumptions**.
  - **Blockers** (what you're waiting on, from which laptop) and **stubs** you created for not-yet-built dependencies.
  - **Status roll-up** of all 28 DATA tasks (REAL/SCAFFOLD/MOCK + done/in-progress).

---

## 3. Ownership, directories & git/merge discipline

### 3.1 What you own / may edit
- **Own (full read/write):** everything under **`data/`**.
- **Own log:** `docs/laptops/01-data.md`.
- **Append-only:** `CONTEXT.md`, `TODO.md`.
- **Read-only (never edit):** `BACKEND.md`, every other laptop's directory (`ml/`, `backend/`, `frontend/`, `db/`, `infra/`, `platform/`, `.github/`, root compose), and other laptops' logs.

### 3.2 Suggested `data/` layout (create as you go; mirror BUILD_PLAN deliverable paths)
```
data/
  schemas/          l0_event.py, l0_event.avsc, l0_event.proto, sample_event.json
  registry/         schema_registry config + compatibility policy
  infra/kafka/      topic definitions (events, alerts, audit, signals), producer/consumer clients
  streaming/flink_jobs/   base stateful job (checkpointing, keyed state), windowed-feature jobs
  ingest/           normalizer.py, recon/swift_cbs_join.py, reliability/ (dedupe/DLQ/backpressure), count_recon.py
  feature_store/    feature_repo/ (Feast), redis online config
  sim/              simulator.py, population.py, normal_behaviour.py, scenarios/, labels.py, augment.py, config
  datasets/         loaders/ (CERT/IEEE-CIS/ULB/PaySim/Elliptic/SPEDIA), splits.py
  connectors/       base_adapter.py, cbs/, payments/, iam_pam/, dlp_dbaudit/, hr_iga/, real_telemetry/
  features/         baselines.py, identity_access.py, transaction.py, data_layer.py, change_hr.py, graph.py, temporal.py, dfs_featuretools.py
  labels/           label_store.py (4 sources)
  governance/       catalog/, classification.py, quality/expectations, retention.py
  mdm/              entity_resolution.py
  lineage/          lineage.py (source->feature->model->alert; dataset hash + feature-set version)
  tests/            unit + integration + contract + data-validation tests
  README.md         how to run the DATA stack locally
  pyproject.toml / requirements.txt   pinned deps
```
You may adapt names, but keep deliverable paths recognizable against the BUILD_PLAN "Deliverable" column and record the final layout in your log.

### 3.3 Git / merge discipline (exact)
- **Branch:** `hawk-eye/data`. Never commit to `main` directly. Branch from latest `main`.
- **Commit message format (mandatory):**
  ```
  [DATA] <TASK-ID> <imperative summary> (blueprint Part <X>)
  ```
  e.g. `[DATA] DATA-9 add fraud-scenario injectors for 8 typologies (blueprint Part 21.1)`.
- **One logical change per commit**; keep commits scoped to tasks so merges stay clean.
- **Only edit files under `data/` + your log + append to shared MD.** Disjoint ownership is what makes the 6-way merge clean — do not break it.
- **Stubbing a not-yet-built dependency from another laptop:** if you need something another laptop owns that isn't merged yet (e.g., PLATFORM's Kafka compose, BACKEND's EDD disposition endpoint, DATABASE's ClickHouse DDL/retention tiering), create a **local stub inside `data/`** (a mock broker via testcontainers/`kafka-python` against a local Redpanda, a fake disposition fixture, a local ClickHouse via docker) so your code runs and tests pass. **Mark the stub clearly**, note it in your log and in `CONTEXT.md`, and write the integration so swapping the real dependency in is a config change, not a rewrite. Never reach into another laptop's directory to "fix" it.
- **Before merging:** run all checks in §8, confirm the blueprint validation gate (§9), update all four MD files (§10).

---

## 4. Tech stack & pinned versions (this workstream)

Pin **exact patch** versions in your lockfile; these come from **blueprint Part 24.3** (l.917–943) and `BACKEND.md` §0. Verify the latest patch before locking and record it in your log.

| Component | Version pin | Role in DATA |
|---|---|---|
| **Apache Kafka** (Redpanda OK as local drop-in) | 3.8.x (or 4.0) | event ingestion (topics: events, alerts, audit, signals) |
| **Apache Flink** | 1.20.x | stateful streaming, keyed per-entity state, sliding/tumbling windows, CEP |
| **Feast** | 0.40.x | feature store — single definition for train & serve |
| **Redis** | 7.4.x | online feature store + per-entity/peer-baseline cache (TTLs) |
| **ClickHouse** | 25.x | history/investigation store + offline feature backfill (you write DDL/sink; DATABASE owns the cluster/tiering) |
| **PostgreSQL** | 17.x | app metadata (read-only awareness; DATABASE owns it) |
| **Python** | 3.12.x | simulator, normalizer, features, loaders, governance, tests |
| **SimPy or Mesa** | current stable | agent-based simulator core |
| **SDV** (CTGAN / TVAE / diffusion) | current stable | generative tabular augmentation (rare-class, feature-space only) |
| **featuretools** | current stable | Deep Feature Synthesis (automated feature generation) |
| **Snorkel** | current stable | programmatic/weak labelling (label-source-2) |
| **Great Expectations / Pandera** | current stable | data validation tests |
| **Avro / Protobuf + schema registry** (Apicurio/Confluent-compatible) | current stable | event schema + evolution governance |
| **DVC and/or MLflow data artifacts** | DVC current / MLflow 2.18.x | dataset versioning + content hash + lineage |
| **pandas / pyarrow** | current stable | Parquet I/O, transforms |
| **kafka-python / confluent-kafka / testcontainers** | current stable | Kafka clients + local integration tests |

**Tooling for lint/format/type/test (Python):** **ruff** (lint), **black** (format), **mypy** (type), **pytest** (test), **Great Expectations/Pandera** (data validation). Pin these too.

> **Rule:** every dependency pinned; no unpinned `latest`. Track CVEs. If a Part-24.3 pin conflicts with a transitive requirement, document the resolution in your log and note it in `CONTEXT.md`.

---

## 5. Interface contracts / the seams (what you consume & produce)

Read `BACKEND.md` for the canonical shapes. Below is **who owns what at each seam you touch**, what you **produce**, what you **consume**, and your **integration responsibility**. Mention every seam even where another laptop owns it — name the owner and your duty.

### 5.1 L0 event schema — **DATA OWNS** (BACKEND/ML/DATABASE consume)
- **You produce** the canonical **actor → action → object** event with field groups **Actor / Action / Object / Context / Linkage** (blueprint 5.1, `BACKEND.md` §1). The JSON example lives in `BACKEND.md` §1 and Part 24.5(a) — your `schemas/l0_event.*` MUST match it field-for-field. **Linkage** = correlation keys joining SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account.
- **Consumers:** BACKEND (L1 rules + fusion), ML (features→models), DATABASE (ClickHouse events table). FRONTEND visualizes the field groups in the entity-360 timeline.
- **Your duty:** publish the schema + sample payload, register it in the schema registry, and announce it in `CONTEXT.md`. Any field change goes through `CONTEXT.md`→`[BACKEND]`.

### 5.2 L1 rules / BRE + SoD/toxic-combination matrix — **BACKEND OWNS the engine** (you supply the stream)
- **BACKEND owns** the rules engine and the SoD/toxic-combination matrix (BACKEND-5..8). **You supply** the L0 event stream + the Redis online features it consumes, **and** the **SWIFT↔CBS reconciliation join** as a *signal feature* (the recon mismatch itself is your DATA-16 deliverable; BACKEND turns it into a rule hit).
- **Your duty:** ensure the features named in the blueprint typologies (off-hours, new-beneficiary→high-value latency, DB-write-without-app-txn, dormant reactivation, entitlement self-grant) exist in your feature store so BACKEND's L1 can read them. Coordinate the feature key names in `CONTEXT.md`.

### 5.3 Feature store (Feast/Redis) — **DATA OWNS** (ML & BACKEND read)
- **You define and materialize** features in Feast with a **single definition for train & serve** (no train/serve skew), serve online via **Redis**, and backfill offline in **ClickHouse** with identical definitions.
- **Consumers:** ML reads features for training/inference of L2–L6; BACKEND reads online features in the hot path.
- **Your duty:** publish the **feature names, entity keys, and windows** in `CONTEXT.md`; guarantee identical feature logic online (Flink→Redis) and offline (ClickHouse backfill). Redis is provisioned by DATABASE (port 6379) and Feast online store config is yours.

### 5.4 Models L2–L6 — **ML OWNS** (you feed them)
- ML trains/produces artifacts. **You do not build models.** You feed ML the features (5.3), the labelled datasets, the leakage-safe splits (DATA-24), and the label store (DATA-23).
- **Your duty:** deliver `datasets/splits.py` (temporal + entity-disjoint + leaky-feature removal) and the four-source label store so ML can train honestly. Lineage (DATA-25) records dataset hash + feature-set version per model — ML's registry consumes this.

### 5.5 Model storage/registry — **DATABASE OWNS object store + registry layout** (ML owns MLflow/ONNX)
- You **write into** the object store (MinIO/S3 — DATABASE owns the buckets `datasets`, `feature-snapshots`) your partitioned Parquet datasets and feature snapshots, and you record curated-set versions (DVC/MLflow). You do **not** own the bucket policy or retention tiering — DATABASE does.
- **Your duty (DATA-25):** coordinate the dataset-Parquet partition layout (by date/source) and the `datasets`/`feature-snapshots` bucket usage with DATABASE in `CONTEXT.md`. Your retention-tiering writes depend on **DATABASE-RETENTION-TIERING**; stub a local MinIO until it lands.

### 5.6 PII tokenization — **BACKEND OWNS the tokenizer + vault; PLATFORM owns HMAC key/secrets**
- You do **not** build the tokenizer. But your **data classification (DATA-26)** tags which L0 fields are PII/PAN/sensitive — that classification **drives** BACKEND's masking and the re-identification policy. Your synthetic data must already use **tokenized-style synthetic IDs** (`EMP-*`, `ACCT-*`, `BEN-*`) so no real PII ever exists; this is also your golden-rule-2 compliance.
- **Your duty:** publish the classification tags so BACKEND/PLATFORM mask/encrypt the right fields. Never emit real PII; synthetic-only.

### 5.7 Source connectors — **DATA OWNS the adapters/mock fixtures; PLATFORM owns the integration runtime**
- **You own** the per-source adapters and their **mock fixtures** (CBS, SWIFT/RTGS/NEFT/IMPS/UPI, IAM/AD, PAM, IGA, HR, DB-audit/DLP). **PLATFORM owns** the integration runtime (api-gateway, schema-registry *hosting*, reliability infra deployment). You define the schema-registry *content & compatibility policy*; PLATFORM hosts it.
- **Your duty:** ship connectors as **SCAFFOLD** (read mock fixtures into L0 now; swap to live feeds later with a config change). Coordinate runtime/hosting with PLATFORM in `CONTEXT.md`.

### 5.8 Audit/WORM — **DATABASE OWNS the immutable store; BACKEND writes audit events**
- Your **lineage and DQ records** may be archived to the WORM/audit-archive store, but **DATABASE owns** it. You write through the interfaces they expose.
- **Your duty:** keep lineage records immutable-friendly (append-only, hashed) and coordinate the archive path with DATABASE.

### 5.9 EDD feedback loop — **BACKEND owns the disposition API; you own label-source-4 ingestion**
- **label-source-4** (EDD feedback: fraud/FP/inconclusive per alert) arrives via BACKEND's `POST /alerts/{id}/disposition` (`BACKEND.md` §5). You **ingest those dispositions into the label store** (DATA-23). This is a **MOCK** until BACKEND's endpoint exists — stub it with the §5 response fixture.
- **Your duty:** match the disposition/label payload shape in `BACKEND.md` §5 exactly; depend on **BACKEND-EDD-DISPOSITION-API**; stub until live.

### 5.10 Runtime provisioning — **PLATFORM owns** (you consume)
- PLATFORM provisions the Kafka/Flink/Redis/ClickHouse/MinIO runtime and the docker-compose walking skeleton (**PLATFORM-1**). Ports per `CONTEXT.md` §7: Kafka 9092, ClickHouse 8123/9000, Redis 6379, MinIO 9001/9002.
- **Your duty:** depend on **PLATFORM-1**; until it lands, stub locally (Redpanda/ClickHouse/Redis/MinIO via your own docker for tests). Do not edit `infra/` or root compose.

---

## 6. Your complete task list (every task, grouped by milestone)

Format per task: **ID · what · deliverable path · status · blueprint ref · acceptance check.** All 28 tasks below collectively cover **every** item in `ws_DATA.json` (44 inventory items) and **every** must-cover capability. A task is **done only when its acceptance check passes and the blueprint Part requirement is validated.**

### M1 — Foundations: Schema & Streaming Substrate

- **DATA-1 · L0 Unified Event Model (canonical actor→action→object)** · `data/schemas/l0_event.py` + `l0_event.avsc` + `l0_event.proto` + `sample_event.json` · **REAL** · *Part 5.1 (l.162–173), Part 24.5(a) (l.963–976); matches `BACKEND.md` §1.* · **Accept:** schema has all five field groups (Actor: employee_id, role, dept, branch, tenure_days, manager_id, leaver_flag, peer_group, privileged_flag; Action: verb, channel, maker_checker; Object: account_id, beneficiary_id, table/dataset, entitlement_id, instrument, amount, currency; Context: ts, src_ip, device, geo, session_id, layer, is_off_hours, host; Linkage: correlation keys SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account); sample payload validates against the schema and is byte-compatible with `BACKEND.md` §1; announced in `CONTEXT.md`.

- **DATA-2 · Schema registry, versioning & evolution governance** · `data/registry/` (config + compatibility policy) · **REAL** · *Part 28.2 (l.1206), Part 32.1 (l.1302).* · **Accept:** L0 schema registered (Avro/Protobuf); a documented **backward/forward-compatible** evolution policy; a negative test proves a breaking change is rejected and a compatible one accepted. (PLATFORM hosts the registry runtime — coordinate.)

- **DATA-3 · Kafka ingestion cluster + topic topology** · `data/infra/kafka/` (topic defs + producer/consumer clients) · **REAL** · *Part 8 event ingestion (l.299).* · **Accept:** topics `events`(.raw/.signals), `alerts`, `audit` defined with partitioning keyed by entity; Redpanda-compatible producer/consumer round-trips an L0 event locally; depends on **PLATFORM-1** (stub with local Redpanda until then).

- **DATA-4 · Flink stateful stream processor scaffold** · `data/streaming/flink_jobs/` (base job) · **REAL** · *Part 8 stream processing (l.300), Part 6 engineering note (l.259).* · **Accept:** a base Flink job with **checkpointing** and **keyed per-entity state**, consuming `events.raw`, demonstrating a sliding/tumbling window; runs locally on the simulator stream.

- **DATA-5 · Normalization/ingest layer → Kafka (hot) + ClickHouse (history)** · `data/ingest/normalizer.py` + ClickHouse events-table DDL/sink · **REAL** · *Part 5.1 (l.173).* · **Accept:** `normalizer.py` maps a raw source row to a valid L0 event and lands it in Kafka `events.raw` **and** a ClickHouse `events` table (DDL coordinated with DATABASE; stub local ClickHouse until DATABASE-CLICKHOUSE lands). Depends on **PLATFORM-1**, **DATA-1**, **DATA-3**.

- **DATA-6 · Feast + Redis online feature store (single train/serve definition)** · `data/feature_store/feature_repo/` (Feast) + Redis online config · **REAL** · *Part 8 online feature store (l.301), Part 6 engineering note (l.259).* · **Accept:** a Feast repo with at least one entity (employee) and feature view; `feast apply` succeeds; an online read from Redis returns a materialized feature; **same definition** is used for offline (ClickHouse) — proven in DATA-22.

### M2 — Synthetic Simulator & Public Datasets

- **DATA-7 · Agent-based synthetic simulator core (SimPy/Mesa harness)** · `data/sim/simulator.py` · **REAL** · *Part 21.1 (l.791–808), Part 5.5 (l.203–206).* · **Accept:** a SimPy/Mesa harness emitting **labelled Parquet** *and* a **Kafka stream** in the L0 schema; deterministic with a fixed seed; runs end-to-end on a small config. Depends on **DATA-1**, **DATA-3**.

- **DATA-8 · Population + normal-behaviour models** · `data/sim/population.py` + `data/sim/normal_behaviour.py` · **REAL** · *Part 21.1 #1–#2 (l.795–796).* · **Accept:** `population.py` generates N employees with `role, department, branch, tenure, manager, peer_group, privileged_flag` mirroring an org shape (configurable up to ~50k staff, a few hundred privileged); `normal_behaviour.py` has **per-role activity generators** with **diurnal/weekly rhythms** (tellers in branch hours, DBAs nightly batch, ops makers/checkers pairing, analysts dispositioning) emitting transaction/access/data-layer/change events with realistic volumes and noise.

- **DATA-9 · Fraud-scenario injectors + red-team typology library** · `data/sim/scenarios/` (one module per typology) · **REAL** · *Part 21.1 #3 (l.797–805), Part 5.5 (l.206), Part 0 (l.29), Part 12 coverage map (l.403–425).* · **Accept:** **one module per typology**, each producing a labelled trace embedded in normal traffic, covering the **eight fast-lane + four slow-lane named typologies**. **Fast lane:** (1) **beneficiary-then-approve** (new payee→high-value by same maker/checker), (2) **dormant-account takeover** (reactivation→silent channel enrollment→drain), (3) **SWIFT-without-CBS** (instrument msg with no matching CBS posting — the PNB mechanism), (4) **suspense/nostro lapping** (aging items; same actor posts+reconciles), (5) **privilege self-grant** (short-lived entitlement timed around a fraudulent approval), (6) **bulk exfiltration before resignation** (download spike in notice-period window), (7) **maker-checker collusion ring** (recurring colluding pair/cluster — feeds the graph layer), (8) **rogue-trader** (no-leave + late/cancelled-rebooked trades **+ P&L-vs-mark / mismarking divergence**). **Slow lane (Part 12 coverage map, l.415–419):** (9) **fake-vendor / billing fraud** (vendor address = employee address; round/sequential invoice numbers; single-client vendor), (10) **ghost employees / payroll** (no tax footprint; duplicated bank details across payees), (11) **alert suppression by AML watchers** (one analyst clearing a disproportionate share of alerts; reopened-then-cleared pattern), (12) **ghost / insider loans + inflated appraisal** (thin documentation; appraiser-is-borrower; disbursement to a non-sanctioned account). Each typology is toggleable, emits ground-truth-tagged events, and carries a **`lane: fast|slow`** tag so BACKEND's slow-lane scorer (`BACKEND-25`) and the EWS/RFA feed consume the slow-lane traces. (Note: slow-lane schemes surface over weeks/months — the simulator still injects them with ground truth so the slow-lane features and EWS scoring can be validated; do not claim real-time detection for them.)

- **DATA-10 · Ground-truth labelling + scale knobs + worked end-to-end scenario** · `data/sim/labels.py` + scale config + replayable burst scenario · **REAL** · *Part 21.1 #4 (l.806), Part 21.1 scale (l.808), Part 24.5(d) (l.1016–1025).* · **Accept:** every event tagged `is_fraud`, `scenario_id`, `actor_id`, `ring_id`; **scale knobs** for number of agents, time span (configurable to ~18 months), and a **realistic rare fraud rate (~0.1–1%)**; a **replayable worked burst** reproduces the Part 24.5(d) sequence: `create_beneficiary` off-hours → `approve_payment` INR 48,00,000 → graph edge → (downstream L6 fusion risk 87 → narrative) — i.e., the simulator emits exactly this labelled positive on demand.

- **DATA-11 · Generative tabular augmentation (rare-class only)** · `data/sim/augment.py` (SDV CTGAN/TVAE/diffusion) · **REAL** · *Part 21.2 (l.810–811), Part 5.5 (l.207–208).* · **Accept:** SDV-based oversampling of the **minority class only**, **in feature space only**, anchored to real/simulated distributions, with **conditional/entity-aware** sampling and **imbalance-handling hooks** (negative subsampling 1:3–1:10 + class weights/focal-loss handoff). **Document the caveat** (naive tabular GANs break behavioural patterns — inter-event timing/velocity/multi-account motifs — so behavioural realism comes only from the agent simulator; generative is feature-space padding) in code docstring and your log. Never evaluate models on synthetic-only.

- **DATA-12 · Public/benchmark dataset loaders + references** · `data/datasets/loaders/` · **REAL** · *Part 5.3 (l.182–194), Part 17.B (l.518–523), Part 0 (l.29).* · **Accept:** loaders that map each public dataset to the L0 schema (or a documented feature-space form), for **CMU-SEI CERT (r4.2/r5.2/r6.2)**, **IEEE-CIS Fraud (Vesta)**, **ULB Credit-Card Fraud**, **PaySim**, **Elliptic**, **SPEDIA / Amazon Fraud-Dataset-Benchmark**. Each loader documents the dataset's **purpose** (CERT→insider L2/L4; IEEE-CIS→tabular L3; ULB→extreme-imbalance test; PaySim→scale test **with leakage caveat**; Elliptic→graph L5; SPEDIA/FDB→broader benchmarking) and its **leakage caveats** (PaySim balance columns). State the honest stance: **no drop-in pre-trained model exists for the bank**; public data is for prototyping/transfer only.

### M3 — Source Connectors (mock/scaffold) & Reliable Ingestion

- **DATA-13 · Transaction-source connectors** · `data/connectors/cbs/` + `data/connectors/payments/` · **SCAFFOLD** · *Part 5.2 (l.175–180), Part 32.1 (l.1292–1299), Part 9.1 (l.327,330).* · **Accept:** adapters shaped for **CBS (Finacle/Flexcube/BaNCS/T24)** posting logs and **Payments (SWIFT/RTGS/NEFT/IMPS/UPI)** message logs, plus **GL/suspense/nostro** and **trade/treasury blotter**, each **reading mock fixtures into L0**. Code is complete and correct; live feeds require real credentials (hence SCAFFOLD). Mock fixtures live in the connector dir.

- **DATA-14 · Identity/access + data-layer + change/HR connectors** · `data/connectors/iam_pam/` + `dlp_dbaudit/` + `hr_iga/` · **SCAFFOLD** · *Part 5.2 (l.178–180), Part 32.1 (l.1295–1299), Part 9.1.* · **Accept:** adapters for **IAM/AD** auth logs, **PAM (CyberArk/BeyondTrust)** privileged-session logs, **VPN**; **DB-audit** + **DLP/egress** + bulk-download/export records; **HR/HRMS joiner-mover-leaver** feed + **IGA/entitlement-change** logs + account-modification logs — each reading mock fixtures into L0. SCAFFOLD (live feeds need creds). The HR JML feed is flagged as the single highest-value context signal.

- **DATA-15 · Unified ingestion-adapter framework + CDC/batch pattern + collectors** · `data/connectors/base_adapter.py` + CDC/batch + read-only collector agents · **SCAFFOLD** · *Part 32.1 pattern (l.1300), Part 9.1/9.3 (l.327,330,366).* · **Accept:** a `base_adapter.py` interface all connectors implement; a **CDC→Kafka streaming** path (low latency) and a **periodic-batch (slow-lane)** path; **read-only collector agents** modelling reads from CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR. SCAFFOLD until live feeds.

- **DATA-16 · SWIFT↔CBS reconciliation join (the PNB control)** · `data/ingest/recon/swift_cbs_join.py` · **REAL** · *Part 32.1 (l.1294), Part 6.2 (l.232), Part 5.5/21.1 SWIFT-without-CBS typology.* · **Accept:** a join that matches SWIFT/instrument messages to CBS postings and emits a **reconciliation-mismatch signal** (instrument with no CBS entry) onto `events.signals`; validated against the DATA-9 SWIFT-without-CBS synthetic typology (it fires on the injected fraud, stays quiet on matched pairs). This is REAL on synthetic data and is the feature BACKEND's L1 turns into a rule.

- **DATA-17 · Ingestion reliability + feed-loss reconciliation + source-onboarding playbook** · `data/ingest/reliability/` + `data/ingest/count_recon.py` + `docs/source_onboarding_playbook.md` · **REAL** · *Part 32.2 (l.1304–1306), Part 32.3 (l.1308–1309), Part 18 (l.590).* · **Accept:** **idempotent dedupe by deterministic event_id**, **dead-letter queue** for poison messages, **backpressure** hooks, retries-with-backoff (and awareness of circuit-breaker/bulkhead patterns BACKEND/PLATFORM own); **periodic reconciliation of ingested counts vs source-of-truth** to detect silent feed loss; a **repeatable source-onboarding playbook** doc: discovery → schema mapping → connector build → DQ rules → backfill → lineage validation → shadow → promote, with onboarding-status tracking on the program dashboard. (Note: `docs/` is shared; place the playbook under `data/docs/` or coordinate the `docs/` path in `CONTEXT.md` — do not collide with another laptop.)

- **DATA-18 · Real-telemetry ingestion + label-sourcing scaffold** · `data/connectors/real_telemetry/` · **SCAFFOLD** · *Part 21.3 (l.813–815), Part 5.2/5.4.* · **Accept:** a scaffold mapping real **CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR** feeds into the L0 model, with hooks for **gold historical** / **weak** / **EDD** labels and **PU-learning/semi-supervised** entry points. SCAFFOLD — awaits live feeds + real labelled bank fraud data (explicitly unavailable). Depends on **DATA-15**, **DATA-23**.

### M4 — Feature Engineering & Feature Store

- **DATA-19 · Three-way baseline framework (per-entity, per-peer-group, global) with time decay** · `data/features/baselines.py` + Redis caching · **REAL** · *Part 6 intro (l.212–214), Part 18.1 (l.592).* · **Accept:** baselines computed **three ways simultaneously** — per-entity (user vs own history), per-peer-group (user vs same role/branch/dept), global — each with **time decay**; **Redis caching** of per-entity + peer-group stats with **TTLs**, recomputed **on a schedule** (not per event). This is the antidote to low-and-slow baseline poisoning.

- **DATA-20 · Identity/access + transaction feature families** · `data/features/identity_access.py` + `data/features/transaction.py` · **REAL** · *Part 6.1 (l.216–222), Part 6.2 (l.224–233).* · **Accept:** **identity_access.py** implements **every** 6.1 feature: off-hours/odd-hours score (vs personal & peer) + first-time-after-hours flag; login velocity, failed→success bursts, impossible-travel, new-device/new-geo; **dormant-account reactivation→activity**; **privilege-escalation** events, entitlement-change velocity, **acting-outside-role** (peer deviation); session-duration anomaly; concurrent-session anomaly; **"no-leave-taken" streak**. **transaction.py** implements **every** 6.2 feature: amount z-score (personal/peer), **just-under-threshold** clustering, round-number bias; velocity in sliding windows + burst; **new-beneficiary→high-value-payment latency**; **maker-checker pairing frequency**; reversal clustering per operator; fee/charge/rate-override frequency on linked accounts; **suspense/nostro item aging + same-person post-and-reconcile**; **SWIFT↔CBS reconciliation mismatch** (consumes DATA-16); standing-instruction/beneficiary-modification events; **P&L-vs-mark / mismarking divergence** (trader reported mark vs independent/observed valuation drift — the rogue-trading slow signal); **per-analyst alert-clear-rate disproportion + reopened-then-cleared** pattern (the AML alert-suppression signal, Part 12 l.416). Each feature has a unit test asserting it fires on the relevant synthetic typology.

- **DATA-21 · Data-layer + change/HR + graph + temporal feature families** · `data/features/data_layer.py` + `change_hr.py` + `graph.py` + `temporal.py` · **REAL** · *Part 6.3 (l.235–240), Part 6.4 (l.242–246), Part 6.5 (l.248–252), Part 6.6 (l.254–257).* · **Accept:** **data_layer.py** (6.3): export volume vs baseline + **bulk-export flag** + export-to-personal-channel; **DB write/update with no corresponding application transaction**; sensitive-table/PII/PAN access outside role + unusual query shapes; logging-config/audit-setting changes (**log-tampering proxy**); shared/service/orphaned-account use + dormant-privileged activation. **change_hr.py** (6.4): **entitlement self-grant** + short-lived grants timed around transactions; role-change recency/tenure/**leaver-notice-period window**; **referrer-cluster** signal; **toxic-combination flags** (holds conflicting entitlements / acted on a self-granted right). **graph.py** (6.5, feeds L5): degree/centrality in beneficiary/counterparty graph; shared device/IP/address/phone links between employees and beneficiaries; circular-flow/round-tripping/mule-chain motifs; maker-checker collusion subgraphs; employee↔customer-account linkage. **temporal.py** (6.6, feeds L4): behavioural drift vs rolling baseline; change-point detection; session action-sequence features (order + timing); periodicity breaks (e.g., end-of-period manual journals). **Slow-lane signal features (Part 12 coverage map, l.415–419):** in `graph.py` — **vendor-address = employee-address**, **single-client vendor**, and **round/sequential invoice numbering** (fake-vendor/billing), plus **duplicated bank-details clusters** (ghost-employee/payroll); in `change_hr.py` — **appraiser-is-borrower** and **disbursement-to-non-sanctioned-account** (ghost/insider loan + inflated appraisal), plus a **no-tax-footprint** flag (ghost employee). These back the Part-12 slow-lane coverage claims and feed L5 / the slow-lane scorer. Each family has tests against the synthetic typologies.

- **DATA-22 · Streaming compute, online serving, offline backfill, automated feature generation** · Flink windowed-feature jobs + Feast/Redis online + ClickHouse offline backfill + `data/features/dfs_featuretools.py` · **REAL** · *Part 6 engineering note (l.259).* · **Accept:** Flink jobs compute **sliding/tumbling windowed features keyed per-entity**; Feast/Redis serves them online (sub-ms target); **ClickHouse offline backfill uses identical feature definitions** (prove train/serve-skew avoidance with a parity test: same input → same online and offline value); a **featuretools Deep Feature Synthesis** module auto-generates aggregation features. Depends on **DATA-20**, **DATA-21**, **DATA-6**.

### M5 — Labels, Datasets, Governance, Quality & Lineage

- **DATA-23 · Label sourcing: all four channels** · `data/labels/label_store.py` (+ gold-case mock fixtures) · **MOCK** · *Part 5.4 (l.196–201), Part 21.3 (l.813–815).* · **Accept:** a label store unifying **(1) gold historical** Vigilance/CBI/forensic-audit case outcomes as positive labels (**MOCK** seeded fixtures — real labelled bank fraud unavailable), **(2) weak/heuristic labels** from Layer-1 rule hits via **Snorkel-style programmatic labelling**, **(3) synthetic red-team injection** positives (from DATA-10 ground truth), **(4) EDD feedback** (fraud/FP/inconclusive) ingested from BACKEND's `POST /alerts/{id}/disposition` (`BACKEND.md` §5 — stub the response until **BACKEND-EDD-DISPOSITION-API** lands). Provide **PU-learning/semi-supervised** entry points to exploit the unlabelled majority. Overall status MOCK because (1) is seeded and (4) depends on a not-yet-built endpoint.

- **DATA-24 · Splits & leakage avoidance** · `data/datasets/splits.py` · **REAL** · *Part 21.4 (l.817–820), Part 14 leakage pitfalls (l.475–479).* · **Accept:** **temporal split** (train on past, validate/test on future — never random); **entity-disjoint** validation (no employee leaks across splits); **leaky-feature removal** (e.g., PaySim balance columns; any field encoding the label). A test proves a randomly-split baseline is rejected and a temporal split is enforced; a leaky feature is detected and dropped. Depends on **DATA-12**, **DATA-22**, **DATA-23**.

- **DATA-25 · Dataset storage, versioning & lineage** · ClickHouse + MinIO/S3 partitioned Parquet + DVC/MLflow versioning + `data/lineage/lineage.py` · **REAL** · *Part 21.5 (l.822–826), Part 28.2 lineage (l.1205).* · **Accept:** raw events in **ClickHouse + object store (MinIO/S3) as partitioned Parquet (by date/source)**; curated training sets **versioned with DVC and/or MLflow data artifacts**, each carrying a **content hash**; **Feast offline store** used; **end-to-end lineage** (source→feature→model→alert) recorded so every model can record the **dataset hash + feature-set version** it trained on. Depends on **DATA-24**, **DATABASE-RETENTION-TIERING** (stub MinIO locally until DATABASE lands). Coordinate bucket/partition layout with DATABASE in `CONTEXT.md`.

- **DATA-26 · Data catalog, dictionary, classification & MDM/entity resolution** · `data/governance/catalog/` + `data/governance/classification.py` + `data/mdm/entity_resolution.py` · **REAL** · *Part 28.2 (l.1202–1203, l.1207).* · **Accept:** a **data catalog + dictionary** documenting **every L0 field** (owner + description + type); **data classification** tagging **PII/PAN/sensitive vs operational** (drives masking/access/retention — published for BACKEND/PLATFORM, seam 5.6); **MDM/entity resolution** resolving **one employee / one customer identity across CBS/HR/IAM** (essential for entity-360 and the graph layer). Depends on **DATA-1**, **DATA-25**.

- **DATA-27 · Data quality + validation tests + retention/minimization governance** · `data/governance/quality/expectations/` + `data/governance/retention.py` · **REAL** · *Part 28.2 quality (l.1204), Part 28.1 (l.1197), Part 31.1 (l.1261).* · **Accept:** **Great Expectations / Pandera** ingestion validation rules — **completeness, validity, freshness, schema conformance, range/null, distribution checks** — with **DQ SLAs + a dashboard hook**; **purpose-bound retention timelines** + automated lifecycle deletion + **erasure with legal/fraud-investigation carve-outs** (data minimization & purpose limitation). A failing-data fixture is caught by the validation suite. Depends on **DATA-26**.

- **DATA-28 · Phase-0 foundations integration milestone** · end-to-end Phase-0 wiring · **REAL** · *Part 13 Phase 0 (l.433–437).* · **Accept:** end-to-end Phase-0 path live: **Kafka + ClickHouse + L0 model** up; **synthetic transactions + IAM/PAM ingested**; the **simulator red-team library streaming**; a **shadow-mode-ready data path** that BACKEND's L1 BRE (with SoD/toxic-combination matrix) can consume; end-to-end event flow demonstrated and baseline alert volume measurable. Depends on **DATA-5**, **DATA-9**, **DATA-22**. This is your integration capstone with BACKEND (L1) and ML (L2/L6).

> **Inventory cross-check (do not skip):** the 44 items in `ws_DATA.json` map onto these 28 tasks as follows — L0 schema items → DATA-1/DATA-2/DATA-5; red-team simulator + typologies → DATA-7/8/9/10; public datasets → DATA-12; the four label sources + PU/semi-supervised → DATA-23 (and DATA-18); connectors (CBS/SWIFT/RTGS/NEFT/IMPS/UPI, GL/suspense/nostro, treasury, IAM/AD/PAM/VPN, DB-audit/DLP, HR/IGA, collectors, read-only integration) → DATA-13/14/15/18; Kafka/Flink → DATA-3/4; Feast/Redis → DATA-6; baselines + Redis caching → DATA-19; full feature catalogue 6.1–6.6 → DATA-20/21; streaming/online/offline/DFS → DATA-22; SWIFT↔CBS recon → DATA-16; CDC/batch + reliability + count-recon + onboarding playbook → DATA-15/17; generative augmentation → DATA-11; splits/leakage → DATA-24; storage/versioning/lineage → DATA-25; catalog/classification/quality/lineage/schema-registry/MDM/retention → DATA-2/26/27; Phase-0 + dataset cheat-sheet → DATA-28/DATA-12; worked burst + sample event → DATA-1/DATA-10. **Every inventory item is represented. Self-check must come up empty.**

---

## 7. Detailed build instructions per milestone (blueprint specifics — nothing lost)

### M1 specifics
- **L0 schema (DATA-1):** Exactly the field groups in `BACKEND.md` §1 / blueprint 5.1. IDs follow `CONTEXT.md` §6: `event_id` = `evt_*`, `entity_id` = `employee_id` (`EMP-7f3a`), `ring_id` = `RNG-*`, `audit_id` = `aud_*`. **Time** is UTC ISO-8601 (`...Z`). **Money** in integer minor units where possible, currency explicit (INR default). `is_off_hours` is a context boolean. `layer` distinguishes `application` vs `database`. Provide `.avsc` and `.proto` for the schema registry and the streaming serializers.
- **Schema registry (DATA-2):** compatibility = **BACKWARD** (or BACKWARD_TRANSITIVE) so a CBS upgrade can't silently break features; document the rule. Coordinate hosting with PLATFORM (5.7).
- **Kafka topology (DATA-3):** partition by entity (employee_id) for parallelism and ordering per entity. Topics: `events.raw`, `events.signals` (recon/derived), `alerts`, `audit`. Redpanda is the local drop-in.
- **Flink (DATA-4):** enable checkpointing; keyed state per entity; demonstrate a sliding window (e.g., 1h velocity) and a tumbling window. Keep deep nets out of the hot path (Part 18.1 design rule) — your Flink jobs compute features and signals, not L4/L5 models.
- **Normalizer (DATA-5):** raw row → L0 event; idempotent (deterministic event_id); writes both Kafka (hot) and ClickHouse (history). ClickHouse DDL coordinated with DATABASE.
- **Feast/Redis (DATA-6):** one feature definition serves both train and serve; Redis is the online store (port 6379, DATABASE-provisioned).

### M2 specifics
- **Simulator (DATA-7/8/9/10):** Use **SimPy or Mesa**; reference **PaySim/MoMTSim** for transaction realism but **prefer agent-based** (it preserves temporal/velocity/multi-account structure that naive GANs destroy). Population mirrors org shape (e.g., 50k staff, a few hundred privileged). Normal-behaviour generators are **per-role** with **diurnal/weekly rhythms**. Fraud injectors = **one module per typology**, **eight fast-lane + four slow-lane** (DATA-9 list), each tagged `lane: fast|slow`. Labels = `is_fraud`, `scenario_id`, `actor_id`, `ring_id`. Scale knobs: agents, time span (~18 months to match CERT), fraud rate **0.1–1% of actors / far fewer events** — keep it rare so models learn true imbalance. Output **Parquet + Kafka**. The **worked burst** (DATA-10) reproduces Part 24.5(d) exactly (create_beneficiary off-hours → approve_payment INR 48L → graph edge → fusion 87 → narrative) and is what the demo/pilot replays.
- **Generative augmentation (DATA-11):** SDV CTGAN/TVAE/diffusion, **rare-class only**, **feature-space only**, **conditional/entity-aware**, anchored to real distributions. Hard rule in docstrings: behavioural realism = agent simulator; generative = tabular feature padding for the supervised layer; **never evaluate on synthetic-only**; imbalance via negative subsampling **1:3–1:10** + class weights/focal loss + post-hoc calibration (calibration itself is ML's job — you provide the data and the subsampling/weights hooks).
- **Public loaders (DATA-12):** map each to L0 or a documented feature form; carry each dataset's purpose + leakage caveats (esp. PaySim balance leakage). State the honest stance from Part 0/5.3: **no drop-in pre-trained model; public data is prototyping/transfer/benchmark only.**

### M3 specifics
- **Connectors (DATA-13/14):** production-shaped adapters per source family (CBS Finacle/Flexcube/BaNCS/T24; SWIFT/RTGS/NEFT/IMPS/UPI; IAM/AD; PAM CyberArk/BeyondTrust; VPN; DB-audit; DLP/egress; HR/HRMS JML; IGA/entitlement), each reading **mock fixtures into L0** → **SCAFFOLD**. Mock fixtures synthetic-only.
- **Framework + pattern (DATA-15):** `base_adapter.py` interface; **CDC→Kafka** (fast lane) + **periodic batch** (slow lane); read-only collector agents.
- **SWIFT↔CBS recon (DATA-16):** the PNB control — join instrument messages to CBS postings; emit mismatch signal; **REAL** on synthetic; validated against the SWIFT-without-CBS typology.
- **Reliability + onboarding (DATA-17):** idempotent dedupe by event_id, DLQ, backpressure, retries-with-backoff; **count reconciliation** vs source-of-truth to catch silent feed loss; the **source-onboarding playbook** doc (discovery→mapping→connector→DQ→backfill→lineage→shadow→promote) with onboarding-status tracking.
- **Real-telemetry scaffold (DATA-18):** maps live feeds to L0 with gold/weak/EDD label hooks + PU/semi-supervised entry points → **SCAFFOLD** (awaits live feeds + real labels).

### M4 specifics
- **Baselines (DATA-19):** per-entity + per-peer-group + global, each time-decayed; Redis-cached with TTLs, recomputed on schedule (Part 18.1). This anchors low-and-slow drift.
- **Feature families (DATA-20/21):** implement **every single feature** in 6.1–6.6 (enumerated in the task entries). Each feature: a clear name (publish the key convention in `CONTEXT.md`), a unit test that fires it on the matching synthetic typology, and the same definition used online and offline.
- **Compute/serve/backfill/DFS (DATA-22):** Flink windowed features keyed per-entity; Feast/Redis online; ClickHouse offline backfill with **identical** definitions (parity test); featuretools DFS for automated aggregation. **Train/serve skew avoidance is a graded acceptance check.**

### M5 specifics
- **Labels (DATA-23):** four sources (gold MOCK, weak via Snorkel, synthetic from DATA-10, EDD from BACKEND §5); PU/semi-supervised hooks. Match `BACKEND.md` §5 payload exactly; stub until BACKEND endpoint exists.
- **Splits (DATA-24):** temporal + entity-disjoint + leaky-feature removal; tests enforce no random split and detect leaky features.
- **Storage/versioning/lineage (DATA-25):** ClickHouse + MinIO/S3 Parquet (date/source partitions); DVC/MLflow content-hashed curated sets; Feast offline; lineage source→feature→model→alert with dataset hash + feature-set version per model.
- **Catalog/classification/MDM (DATA-26):** every L0 field documented/owned/classified; PII/PAN tagging drives masking; MDM resolves one identity across CBS/HR/IAM.
- **Quality/retention (DATA-27):** GE/Pandera completeness/validity/freshness/schema/range/null/distribution + DQ SLAs/dashboard; purpose-bound retention + lifecycle deletion + erasure with fraud carve-outs.
- **Phase-0 (DATA-28):** the end-to-end shadow-ready capstone.

---

## 8. Testing & all checks (commands + what must pass)

Run all of these locally before any merge; they gate every milestone's Definition of Done.

### 8.1 Project setup & dependency pinning
- `pip install -e .` (or `uv sync`) against a **pinned** lockfile (versions from §4 / Part 24.3). No unpinned deps. Record resolved versions in your log.

### 8.2 Lint / format / type
- `ruff check data/` — must pass clean.
- `black --check data/` — must be formatted.
- `mypy data/` — must type-check clean (annotate public functions).

### 8.3 Unit tests
- `pytest data/tests/unit` — cover: L0 schema validation, normalizer mapping, every feature transform (one test per 6.1–6.6 feature asserting it fires on its synthetic typology), baseline decay math, recon join, splits logic, label-store merge, classification tagging, MDM resolution.

### 8.4 Integration tests
- `pytest data/tests/integration` — simulator → Kafka → Flink window → Feast/Redis online read → ClickHouse offline backfill, end-to-end on a small synthetic run (use testcontainers / local Redpanda+ClickHouse+Redis+MinIO when PLATFORM/DATABASE aren't merged). Includes the **DATA-28 Phase-0** end-to-end wiring test.

### 8.5 Contract tests
- Assert the emitted L0 event **validates against `BACKEND.md` §1** and the schema registry; assert the EDD-label ingestion matches `BACKEND.md` §5; assert the **online==offline feature parity** (train/serve-skew test). Schema-registry compatibility test (breaking change rejected).

### 8.6 Domain-specific data tests (your equivalent of ML behavioral/leakage tests)
- **Data validation** (Great Expectations/Pandera): completeness, validity, freshness, schema conformance, range/null, distribution — run on a synthetic batch and on a deliberately-corrupted fixture (must catch it).
- **Leakage tests:** temporal split enforced (random split rejected); entity-disjoint validation; leaky feature (e.g., PaySim balance) detected and removed.
- **Behavioral data tests:** each injected fraud typology produces ground-truth-labelled events that the corresponding feature/signal fires on; benign traffic does not falsely fire the recon/typology signals.
- **Imbalance fidelity:** simulator output holds the configured rare fraud rate (0.1–1%); augmentation stays feature-space + rare-class only.

### 8.7 Performance / latency budgets (where DATA contributes)
- The blueprint online budget (Part 18.1, l.580–586) targets **end-to-end ≤ ~100–300 ms**, with **Kafka ingest + Flink enrichment ~10–40 ms** and **Redis online feature lookup ~1–5 ms**. Add a micro-benchmark asserting your Flink enrichment + Redis feature read stay within these budgets on the local stack; record numbers in your log.

### 8.8 Security / hygiene scans
- Dependency/CVE scan (e.g., `pip-audit`); secret scan (no creds in repo — synthetic only); confirm **no real PII** anywhere. PLATFORM owns the org-wide CI security harness; you ensure your code passes locally.

### 8.9 Definition of Done per milestone (gate)
A milestone is done only when: all its tasks' acceptance checks pass; §8.2–§8.8 are green for the touched code; the blueprint Part is validated and cited; the four MD files are updated; and the work merges cleanly on `hawk-eye/data`.

---

## 9. Blueprint validation gate (each requirement you own → covered)

Tick each only when the acceptance check passes and the Part is validated. Record in `docs/laptops/01-data.md`.

- [ ] **Part 5.1** — L0 unified actor→action→object model, 5 field groups incl. Linkage → DATA-1 (matches `BACKEND.md` §1).
- [ ] **Part 5.2** — all feeds (CBS/SWIFT/RTGS/NEFT/IMPS/UPI, GL/suspense/nostro, treasury; IAM/AD/PAM/VPN; DB-audit/DLP; HR/IGA) → DATA-13/14/15/18.
- [ ] **Part 5.3** — public datasets (CERT/IEEE-CIS/ULB/PaySim/Elliptic/SPEDIA-FDB) + honest "no drop-in model" stance → DATA-12.
- [ ] **Part 5.4** — four label sources + PU/semi-supervised → DATA-23 (+ DATA-18).
- [ ] **Part 5.5** — agent-based simulator + generative caveat + imbalance handling → DATA-7..11.
- [ ] **Part 6 intro** — three-way time-decayed baselines → DATA-19.
- [ ] **Part 6.1** — every identity/access feature → DATA-20.
- [ ] **Part 6.2** — every transaction feature (incl. SWIFT↔CBS mismatch) → DATA-20 (+ DATA-16).
- [ ] **Part 6.3** — every data-layer feature → DATA-21.
- [ ] **Part 6.4** — every change/HR feature incl. toxic-combination flags → DATA-21.
- [ ] **Part 6.5** — every graph feature (feeds L5) → DATA-21.
- [ ] **Part 6.6** — every temporal/sequence feature (feeds L4) → DATA-21.
- [ ] **Part 6 engineering note** — Flink windows + Feast/Redis online + ClickHouse offline parity + featuretools DFS → DATA-22.
- [ ] **Part 8** — Kafka, Flink, Feast+Redis → DATA-3/4/6.
- [ ] **Part 9.1/9.3** — read-only collectors/integration from CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR → DATA-14/15.
- [ ] **Part 12 coverage map** — slow-lane typologies (fake-vendor/billing, ghost-employees/payroll, alert-suppression by AML watchers, ghost/insider-loans+inflated-appraisal) + rogue-trader **P&L-vs-mark mismarking** → injectors DATA-9 + slow-lane features DATA-20/21 (consumed by BACKEND-25 slow-lane scorer & EWS feed).
- [ ] **Part 13 Phase 0** — Kafka+ClickHouse+L0 live, synthetic txns+IAM/PAM, red-team library, shadow-ready → DATA-28.
- [ ] **Part 17.B** — dataset cheat-sheet references → DATA-12.
- [ ] **Part 18.1** — per-entity/peer-baseline Redis caching with TTLs + latency budget → DATA-19 + §8.7.
- [ ] **Part 21.1** — population/normal/injectors(8 fast + 4 slow typologies)/labels/scale → DATA-7..10.
- [ ] **Part 21.2** — generative augmentation rare-class/feature-space → DATA-11.
- [ ] **Part 21.3** — real telemetry + label sourcing + PU/semi → DATA-18/23.
- [ ] **Part 21.4** — temporal + entity-disjoint splits + leaky-feature removal → DATA-24.
- [ ] **Part 21.5** — ClickHouse+MinIO Parquet, DVC/MLflow versioning+hash, Feast offline, lineage → DATA-25.
- [ ] **Part 24.5(a)** — sample unified event payload → DATA-1.
- [ ] **Part 24.5(d)** — worked synthetic burst → alert, replayable → DATA-10.
- [ ] **Part 28.1** — data minimization/purpose/retention/erasure with fraud carve-outs → DATA-27.
- [ ] **Part 28.2** — catalog/dictionary, classification, quality, lineage, schema registry+evolution, MDM, retention → DATA-2/25/26/27.
- [ ] **Part 31.1** — data validation tests (GE/Pandera) → DATA-27 + §8.6.
- [ ] **Part 32.1** — ingestion adapters per source + SWIFT↔CBS recon + CDC/batch + schema governance → DATA-13/14/15/16/2.
- [ ] **Part 32.2** — idempotency/DLQ/backpressure + count reconciliation → DATA-17.
- [ ] **Part 32.3** — repeatable source-onboarding playbook + status tracking → DATA-17.

If any box can't be ticked, it's not done — keep working or raise a blocker in `CONTEXT.md`/`TODO.md §7`.

---

## 10. Definition of Done & handoff

**You are done with the DATA workstream when ALL of the following hold:**

1. **All 28 tasks** meet their acceptance checks at the declared status (REAL/SCAFFOLD/MOCK), and **every box in §9 is ticked** with the Part validated.
2. **All checks in §8 pass** locally: setup, pinned deps, ruff/black/mypy, unit + integration + contract + data-validation/leakage/behavioral tests, latency micro-benchmark, CVE/secret scans, no real PII.
3. **Every inventory item** in `ws_DATA.json` and **every must-cover capability** is represented and built (self-check empty — see §6 cross-check).
4. **The four MD files are updated:**
   - **`CONTEXT.md`** — appended (newest first) with all cross-cutting decisions: L0 schema + registry compatibility, topic names, feature key convention + entity keys + windows, Parquet partition layout, recon signal name, classification tags, any deviations/assumptions, and every dependency stub you created.
   - **`TODO.md`** — DATA rows reflect final state (`[x]` only when blueprint-validated); blockers in §7 tagged + mirrored in `CONTEXT.md`.
   - **`docs/laptops/01-data.md`** — complete log: decisions+Part refs, files created, blueprint validations, deviations, blockers, stubs, and the 28-task status roll-up.
   - **`BACKEND.md`** — you did **not** edit it; any contract change you needed was proposed in `CONTEXT.md` tagged `[BACKEND]`.
5. **Integration handoffs proven:**
   - **BACKEND (L1):** the shadow-ready L0 stream + online features + SWIFT↔CBS recon signal are consumable — DATA-28 demonstrates it.
   - **ML (L2–L6):** the four-source label store, leakage-safe splits, feature store, and lineage (dataset hash + feature-set version) are available for training.
   - **DATABASE:** Parquet partition/bucket layout, ClickHouse events DDL, and retention-tiering write paths are coordinated.
   - **FRONTEND:** L0 field groups (actor/action/object/context) are documented for the entity-360 timeline.
6. **Golden rules upheld throughout:** alert-only (you never block); on-prem + synthetic only (no real PII/feeds/creds); validated-against-blueprint (Parts cited); nothing dropped; stayed in lane (only `data/` + own log + appended shared MD).

**Final integration test:** run the **DATA-28 Phase-0 end-to-end** path — simulator emits the worked burst (DATA-10) → Kafka → Flink windowed features → Feast/Redis online + ClickHouse offline (parity) → SWIFT↔CBS recon signal fires on the injected SWIFT-without-CBS trace → features available for BACKEND L1 and ML L2/L6 — and confirm the labelled positive flows through cleanly. Record the result in your log and announce readiness in `CONTEXT.md`.
