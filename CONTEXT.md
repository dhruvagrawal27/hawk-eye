# CONTEXT.md — Shared Full Context (everyone appends)

> **Purpose.** The single shared brain for all 6 laptops. Read this **first, every session**. When you make a decision that affects anyone else (a schema, an interface, a port, a file location, a convention, a deviation from the blueprint), **append it to the log at the bottom** (newest first) so the other laptops stay in sync. Do not delete others' entries.

---

## 1. What we are building (one paragraph)
Hawk-Eye is a real-time insider & privileged-user fraud-detection platform for a public-sector bank. Telemetry → **L0** unified event model → **L1** rules/BRE → **L2** UEBA/unsupervised → **L3** supervised GBDT → **L4** sequence → **L5** graph → **L6** risk fusion → **L7** investigator dashboard + EDD feedback loop. It **scores and explains; it never auto-blocks**. Built on-prem, local-first, on **synthetic data**.

## 2. Golden rules
1. **Alert-only**, never auto-block. 2. **On-prem + synthetic only** (no real PII/feeds/creds). 3. **Validate every task against the blueprint Part.** 4. **Nothing dropped** — flag missing requirements here. 5. **Stay in your lane** — edit only your owned dirs + your laptop log + append to shared MD.

## 3. Status legend (use everywhere)
- **REAL** — works as real code on synthetic/mock data, locally.
- **SCAFFOLD** — code complete, needs a real external resource to go live (bank feed, cloud creds, API key, HSM/TEE, human validator).
- **MOCK** — hardcoded/simulated stand-in for a human/legal/hardware act (seeded records, generated governance docs, fake attestation service).

## 4. Workstream → owner → directories
| Workstream | Owns | Key contracts it publishes |
|---|---|---|
| DATA | `data/` | L0 event schema, feature names/keys, synthetic dataset format |
| ML | `ml/` | model artifact format, score/reason-code payloads, model-serving inputs |
| BACKEND | `backend/` + **owns `BACKEND.md`** | API routes, alert schema, RBAC, EDD/disposition, tokenization tokens |
| FRONTEND | `frontend/` | — (consumes BACKEND.md) |
| DATABASE | `db/` | table DDLs, storage/retention/registry layout |
| PLATFORM | `platform/`, `infra/`, `.github/`, root compose | runtime, ports, env vars, CI, security/governance mocks |

## 5. The canonical contracts live in `BACKEND.md`
The L0 event JSON, the L6 alert JSON, the API route table, RBAC roles, and the score/reason-code shapes are defined in **`BACKEND.md`** (owned by BACKEND). If you need a change to a contract, propose it here and tag the BACKEND laptop.

## 6. Shared conventions
- **Languages/versions:** see `BACKEND.md` §versions (pinned from blueprint Part 24.3).
- **IDs:** `event_id` `evt_*`, `alert_id` `alr_*`, `entity_id` = `employee_id` (e.g. `EMP-7f3a`), `ring_id` `RNG-*`, `audit_id` `aud_*`.
- **Time:** UTC ISO-8601 (`...Z`); display in IST on the frontend.
- **Money:** integer minor units where possible; currency explicit (INR default).
- **Branch naming:** `hawk-eye/<workstream>` (e.g. `hawk-eye/ml`). **Commit prefix:** `[<WS>] <TASK-ID> message` + blueprint Part cited.

## 7. Ports / service map (PLATFORM maintains)
| Service | Port | Owner |
|---|---|---|
| Kafka | 9092 | PLATFORM/DATA |
| ClickHouse | 8123/9000 | DATABASE |
| Redis | 6379 | DATABASE |
| Postgres | 5432 | DATABASE |
| MinIO | 9001/9002 | DATABASE |
| Backend API (FastAPI) | 8000 | BACKEND |
| Model serving (ONNX/Triton) | 8001 | ML/BACKEND |
| Frontend (Vite) | 5173 | FRONTEND |
| Keycloak | 8080 | PLATFORM/BACKEND |
| MLflow | 5000 | ML |
| Grafana / Prometheus | 3000 / 9090 | PLATFORM |

---

## 8. INTEGRATION LOG — append below (newest first)
> Format: `### YYYY-MM-DD — [WS] — title` then a short note. Append; never overwrite.

### 2026-06-30 — [DATA] — DATA verified 28/28 tasks; proto + parity added
Task-by-task acceptance verification passed; suite 97/97. Added `data/schemas/l0_event.proto` (Kafka/Flink serdes mirror of the L0 dataclass — consumers can codegen from it) and a proven **online==offline feature parity** test (no train/serve skew). Source-onboarding playbook + status tracker added (`data/docs/source_onboarding_playbook.md`, `data/ingest/onboarding_status.py`). No contract changes — L0 fields unchanged.

### 2026-06-30 — [DATA] — DATA workstream M1–M5 landed on `hawk-eye/data`
L0 event model is live in `data/schemas/l0_event.py` (+ `.avsc`, `sample_event.json`) and matches `BACKEND.md` §1 field-for-field (groups Actor/Action/Object/Context/Linkage). **Consumers (BACKEND/ML/DATABASE/FRONTEND): import from `data.schemas`.** Conventions in `data/config.py`: IDs via `make_id`, topics `events.raw`/`events.signals`/`alerts`/`audit` (partition by `employee_id`), **feature-key format `<entity>:<feature>:<window>`**, lanes `fast|slow`.
- **Synthetic data:** `python -m data.sim.cli --employees N --days D` → `data/out/<run>/{events,labels}.{parquet,jsonl}`. Events carry **no label** (leakage-safe); labels are separate, keyed by `event_id`. All 12 typologies (8 fast + 4 slow) emitted; worked burst = `approve_payment` amount **4800000** INR.
- **Feature store (ML/BACKEND read):** `data/features/*` implements every Part-6 feature + slow-lane; `data/feature_store/` exposes a pure-python online store (Redis optional, port 6379).
- **Recon signal:** SWIFT↔CBS mismatch emits `recon_mismatch` on `events.signals` (`data/ingest/recon/swift_cbs_join.py`) — BACKEND L1 turns it into a rule.
- **Runtime:** only numpy/pandas/pyarrow are hard deps; Kafka/Flink/Feast/Redis/ClickHouse/MinIO are guarded with local fallbacks → swap to real infra is a config change. **Stubs awaiting:** PLATFORM-1 (Kafka/Redis/MinIO runtime), DATABASE (ClickHouse DDL + buckets + retention), BACKEND (`POST /alerts/{id}/disposition` for EDD label-source-4). Tests: `python -m data.tests.run` (90 passing; pytest unavailable in env).

### (seed) — [ALL] — Coordination files created
CONTEXT.md, BACKEND.md, TODO.md, and `docs/laptops/*` are live. Read all three shared files before starting. Validate everything against the blueprint.
