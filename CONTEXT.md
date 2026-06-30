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

### 2026-06-30 — [BACKEND] — Validation pass: RBAC conditional cells now enforced + lint/type green
Adversarial audit closed all gaps. Changes others should note: rule-change **approval is Compliance-only** (Team Lead proposes), there is now a **`PUT /rules/{code}`** verb and a **`POST /alerts/{id}/block-request/approve`** (Team Lead) endpoint, model **promotion is Model-Engineer-only**, `view_audit` is **view-own** for Senior/Model-Eng, and **service-account scoped tokens cannot read** alerts/audit. A 2nd Compliance officer (`EMP-co02`) was seeded so four-eyes works within Compliance. Full §8 checks green: ruff + black + mypy clean, 109 pytest. `BACKEND.md §3/§4` updated. (`cargo` checks for `gateway/` deferred to PLATFORM CI — Rust toolchain not local.)

### 2026-06-30 — [BACKEND] — Full backend workstream landed (BACKEND-1..29); BACKEND.md synced
The `backend/` control plane + Rust hot-path tier is complete on synthetic data; **`BACKEND.md` is the live contract — integrate against it, don't guess.** Key seams for the other laptops:
- **DATA:** I consume the L0 event (`BACKEND.md §1`) and read online features by the Feast keys listed in **§1a** (e.g. `minutes_since_new_beneficiary`, `maker_checker_same_actor`, `held_entitlements[]`). I stub these until your Feast/Redis is live — please materialize those keys. The EDD disposition writes labels for your **label-source-4** (`POST /alerts/{id}/disposition`).
- **ML:** model-serving contract in **§6a** (`POST /score` on :8001 → per-layer 0–1 + `model_version`); L6 fusion + plain inline TreeSHAP are mine. Deliver signed ONNX L2/L3/L4 + the L6 meta-model + calibrator; I verify signatures via the registry (DATABASE owns layout). `narrate()` gateway contract in **§7** — I pass tokenized context and persist the audit memo; your route owns NEAR AI→Groq→template failover.
- **DATABASE:** I write every action to your **WORM audit store** (stubbed `app/audit/writer.py`) and read the **model registry** (stubbed `serving/registry.py`); own the Postgres (cases/users/rules/re-id vault) + ClickHouse DDL behind my repository shims.
- **FRONTEND:** every route in **§3** is implemented; OpenAPI at `backend/openapi.json`. Triage queue is ranked by fused risk×exposure×confidence and deduped-per-entity; RBAC is the 8×9 matrix in **§4**; unmask is the separate audited `POST /entities/{id}/unmask`.
- **PLATFORM:** I need Keycloak (OIDC, **§3** auth routes), Vault custody of `PII_HMAC_KEY` + field key + registry signing key, the Kong/APISIX runtime for `backend/gateway_config/kong.yaml`, and mTLS-internal termination. `backend/deploy/docker-compose.backend.yaml` attaches to your external `hawk-eye` network.
- **Invariants enforced everywhere:** ALERT-ONLY (no auto-block, no auto-classify; `block-request` is Analyst→Lead), SoD (deployer can't label/close; four-eyes rule changes; promotion sign-off), audit-write of every action incl. who-viewed-whom. SCAFFOLD only: RBI submission channel (CRILC/FMR), live SIEM, TEE hardware + DPDP jurisdiction confirmation.

### (seed) — [ALL] — Coordination files created
CONTEXT.md, BACKEND.md, TODO.md, and `docs/laptops/*` are live. Read all three shared files before starting. Validate everything against the blueprint.
