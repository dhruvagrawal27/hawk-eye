# Hawk-Eye — Laptop 03: BACKEND — Claude Code Build Prompt

> You are the **BACKEND laptop**. You build `backend/` and you **own `BACKEND.md`**, the integration contract every other laptop binds to. You are the spine: ML models, the frontend, and the databases all integrate through your API, your alert schema, your RBAC, and your tokenization tokens. Build production-shaped code, **local-first on synthetic data**, and keep the contract honest.

---

## 0. Mission & golden rules

**Mission.** Deliver the FastAPI control plane + Rust hot-path tier for the insider-fraud system: Keycloak OIDC auth + short-lived JWTs, an 8-role × 9-capability RBAC matrix with SoD enforcement, the full `/api/v1` surface (alerts, entities, explanations, rules, models, audit, admin, regulatory exports, narratives), the L1 rules/BRE + SoD toxic-combination engine, the online inference + L6 risk-fusion path (ONNX/Triton served through a Rust scoring gateway) with idempotency + graceful degradation, PII tokenization + a re-identification vault, the EDD disposition/feedback write path, audit-write of every action, and the slow-lane EWS/RFA/CRILC/FMR/CFR generators.

**Golden rules (restate at the top of every session — these are non-negotiable):**
1. **ALERT-ONLY.** The system scores, explains, and *requests* a block; a human decides. **Never auto-block money, never auto-classify fraud.** A mandatory human decision (natural justice — SBI v. Rajesh Agarwal, 2023) precedes any fraud classification. `block-request` is Analyst→Lead-approves, never automatic.
2. **ON-PREM + SYNTHETIC ONLY.** No real PII, no real bank feeds, no cloud creds, no live regulator channels. Real external resources → **SCAFFOLD**; human/legal/hardware acts → **MOCK**. All your tasks are REAL or SCAFFOLD (you have zero MOCK).
3. **VALIDATE AGAINST THE BLUEPRINT.** No task is "done" until the matching blueprint Part's requirement is met. Every task below carries a **blueprint ref** and an **acceptance check**. Cite the Part in commits and your laptop log.
4. **NOTHING DROPPED.** Every capability in §6 must be built. If you find a blueprint requirement that is in nobody's lane, raise it in `CONTEXT.md` immediately.
5. **STAY IN YOUR LANE.** Edit only `backend/`, your own log `docs/laptops/03-backend.md`, **and `BACKEND.md` (which you own)**, plus append to the shared `CONTEXT.md` / `TODO.md`. Never edit `data/`, `ml/`, `frontend/`, `db/`, `infra/`, `platform/`, `.github/`, root compose.

---

## 1. Mandatory reading before any code

Read these **at the start of every session**, in this order:
1. **The blueprint** — `Insider_Fraud_Detection_Implementation_Blueprint (2).md`. Read your owned Parts **in full**, skim the rest:
   - **Part 3.1 / 3.4** (~l.74–76, 90–96) — rules are Layer-1, necessary-but-insufficient; SoD/toxic-combination decision; augment-don't-replace (keep SIEM + RBI EWS, build the unifying brain).
   - **Part 20.1** (~l.670–676) — L1 rules/BRE verdict (hybrid rules+ML), named rules, hot-reloadable + versioned + audited.
   - **Part 11** (~l.382–397) — dashboard backend data: triage ranking, entity-360 timeline, explanation panel (rule provenance + SHAP + sequence attention + graph), graph/link view, peer comparison, EDD actions, reporting.
   - **Part 16** (~l.496–503) — RBI compliance: EWS-integrated-with-CBS, RFA tagging, CRILC ₹3-crore/7-day + 180-day window, FMR, CFR, DAMI unit; natural justice (alert-only); data localization; model governance.
   - **Part 18** (~l.553–609) — online + batch inference pipeline, latency budget, idempotency/exactly-once, graceful degradation, model serving & lifecycle.
   - **Part 19.3 / 19.6** (~l.633, 651) — data protection (mTLS, at-rest, field-level PII), dashboard RBAC need-to-know, the SoD key rule, human-in-the-loop.
   - **Part 24** (~l.872–1026) — RBAC matrix (24.1), full API route table (24.2), pinned versions (24.3), UI/screens (24.4), sample payloads (24.5: event/alert/disposition/worked-burst).
   - **Part 25.3 / 25.4 / 25.5** (~l.1041–1067) — PII tokenization HMAC-SHA256 + re-id vault, narrative failover + audit columns, integration sketch.
   - **Part 28.1 / 29.2 / 30.1 / 31.3 / 32 / 33.3** — cross-border/DPDP, human-in-the-loop + watch-the-watchers, graceful degradation, four-eyes rule change, API gateway + reliability patterns, escalation/SLA timers.
2. **`BUILD_PLAN.md`** — the BACKEND section (29 tasks, M1–M5) and the cross-workstream dependency list.
3. **The three shared MD files** — `CONTEXT.md`, `TODO.md`, and **`BACKEND.md`** (you own the last one).

---

## 2. The MD-file coordination protocol (the 4 files, exact rules)

There are **four kinds** of MD files. Obey these rules exactly.

| File | Who owns | Your action |
|---|---|---|
| **`CONTEXT.md`** | shared (everyone appends) | **Read first, every session.** Append every cross-cutting decision/interface/deviation to the **INTEGRATION LOG at the bottom, newest first**, format `### YYYY-MM-DD — [BACKEND] — title`. Never delete others' entries. |
| **`BACKEND.md`** | **YOU OWN IT** | This is the contract all 6 laptops integrate against. **Keep it in sync with the real implementation** as you build: API routes, L0 event shape you consume, L6 alert schema, RBAC roles + SoD rule, disposition request/response, model-serving interface, narrative audit columns, pinned versions. When you change a contract, also note it in `CONTEXT.md` so others see it. Others **only read** this file. |
| **`TODO.md`** | shared (each laptop owns its rows) | Keep the **BACKEND section** current: `[ ]` todo · `[~]` in-progress · `[x]` done (only when blueprint-validated) · `[!]` blocked. Put cross-laptop blockers in §7 and mirror to `CONTEXT.md`. |
| **`docs/laptops/03-backend.md`** | **YOU (your private log)** | Maintain continuously: decisions + rationale, files created, **blueprint validations** (task → Part → how verified), deviations from blueprint (with reason), blockers, stubs you created for not-yet-built dependencies. |

**Ownership statement to restate in your log:** *BACKEND owns `BACKEND.md`; everyone else reads it to integrate. If a non-BACKEND laptop needs a contract change, they propose it in `CONTEXT.md` and tag BACKEND; I (BACKEND) make the edit.*

---

## 3. Ownership, directories & git/merge discipline

- **Owned directories:** `backend/` (all subtrees below it). **Owned MD:** `BACKEND.md`. **Own log:** `docs/laptops/03-backend.md`. **Shared (append-only):** `CONTEXT.md`, `TODO.md`.
- **Branch:** `hawk-eye/backend`. Never commit to `main` directly.
- **Commit format:** `[BACKEND] <TASK-ID> <message> (blueprint Part X)` — e.g. `[BACKEND] BACKEND-6 SoD toxic-combination scoring engine (blueprint Part 3.4/20.1)`.
- **Merge cleanliness:** because ownership is disjoint, merges to `main` are clean. The only shared files you touch are append-only MD — append, never rewrite others' content.
- **Stubbing not-yet-built dependencies (other laptops):** when ML/DATA/DATABASE/PLATFORM deliverables don't exist yet, **build against the `BACKEND.md` contract using local stubs/fakes** under `backend/.../stubs/` or `backend/tests/fakes/`, clearly marked `# STUB: <owner-laptop> <contract>`. Examples: a fake ONNX model-serving endpoint returning deterministic L2/L3 scores; a fake Feast/Redis online-feature reader; a fake ML registry; a fake L6 meta-model + calibrator; an in-memory ClickHouse/Postgres/WORM shim. Stubs must honor the exact contract so swapping in the real component needs no API change. Log every stub in your laptop log and note the seam in `CONTEXT.md`.
- **Definition of "done" gate:** a task is `[x]` only when its blueprint requirement is validated AND its acceptance check passes AND lint/format/type/tests are green.

---

## 4. Tech stack & pinned versions (this workstream)

Pin exact patch versions in lockfiles (`backend/pyproject.toml` + `uv.lock`/`poetry.lock`; `backend/gateway/Cargo.toml` + `Cargo.lock`). Source of truth = **blueprint Part 24.3**; mirror to `BACKEND.md §0`.

| Component | Pin (Part 24.3) | Role in BACKEND |
|---|---|---|
| Python | 3.12.x | API + fusion + rules evaluator + regulatory generators |
| FastAPI / Uvicorn | 0.115.x / 0.32.x | API layer (`/api/v1`) |
| Pydantic | 2.x | request/response schemas, OpenAPI generation |
| Keycloak | 25.x | OIDC/OAuth2 issuer (deployed by PLATFORM; you integrate) |
| OPA (or Drools) | 8.x | entitlement logic / SoD policy bundle / rules engine |
| Rust (axum/actix, `ort`/`candle`) | stable + `ort` bound to ONNX Runtime 1.20.x | hot-path gateways + inline inference |
| ONNX Runtime / Triton | 1.20.x / 25.x | model serving (L2/L3/L4 inline) |
| Kafka / Flink | 3.8.x / 1.20.x | online topology (events/alerts topics; enrich+window) |
| Redis / Feast | 7.4.x / 0.40.x | online feature reads (DATA materializes; you read) |
| ClickHouse | 25.x | event/score history, investigation queries (DATABASE owns DDL) |
| PostgreSQL | 17.x | cases, users, rules, approvals, re-id vault (DATABASE owns DDL) |
| HashiCorp Vault | (PLATFORM-provisioned) | HMAC/PII secret + KMS key custody |
| HMAC-SHA256 | stdlib `hmac`/`hashlib` | deterministic PII tokenization |
| SHAP (TreeSHAP) | per ML pin | inline reason-code contributions |
| Kong / APISIX | gateway (PLATFORM infra) | auth/rate-limit/routing/observability front |
| Prometheus | 3.x | `/metrics` exposition |

Tooling for checks: **ruff**, **black**, **mypy** (Python); **clippy**, **rustfmt** (Rust). Tests: **pytest** (+ `pytest-asyncio`, `httpx` for API contract tests), **cargo test**.

---

## 5. Interface contracts / the seams (what you consume & produce)

**You PRODUCE (and own in `BACKEND.md`):** the L6 alert JSON schema; the full `/api/v1` route table; the RBAC role+capability matrix and SoD rule; the disposition request/response; the tokenization token format (`EMP-7f3a`, `ACCT-4d22`); the model-serving input/output contract; the narrative audit-memo columns. Keep `BACKEND.md` synced as you implement.

**You CONSUME (do not redefine — read from the owner; stub until live):**

| Seam | Owner | Your integration responsibility |
|---|---|---|
| **L0 event schema** | **DATA** | Consume the canonical actor/action/object/context/linkage event (BACKEND.md §1). Do not change it; if you need a field, propose in `CONTEXT.md` and tag DATA. |
| **L1 rules / BRE + SoD/toxic-combination matrix** | **YOU (BACKEND) own the engine**; **DATA supplies the event stream + Redis features** | You build the engine; you read DATA's L0 stream + Feast/Redis features. Stub the feature reader against BACKEND.md §1/§6 until DATA is live. |
| **Feature store (Feast/Redis)** | **DATA** defines & materializes | You **read** online features by Feast keys for rule eval + feature-vector assembly. |
| **Models L2–L6 artifacts (incl. L6 stacked meta-learner + calibrator)** | **ML** trains/produces artifacts; **YOU run the ONLINE fusion + serving + reason-code assembly** | ML hands you signed ONNX artifacts + the L6 meta-model + calibrator + SHAP outputs. You run online L6 fusion (Part 18), assemble reason codes (rule provenance + SHAP + graph). Stub a deterministic meta-model + calibrator until ML delivers. Reference Part 18. |
| **Model storage / registry** | **DATABASE** owns object-store + registry layout + buckets; **ML** owns MLflow tracking + ONNX packaging/signing | Your `/models`, `/models/{id}/promote`, and registry-driven loader **read** the registry + verify signatures; they do not define the bucket/registry layout. |
| **LLM narrative gateway** | **ML** owns the gateway client/prompt/deterministic fallback; **YOU expose `POST /narratives/{alert_id}`**; **PLATFORM** owns egress allow-list + secrets + TEE-attestation MOCK | You expose the route, pass **tokenized** alert context to ML's `narrate()`, persist the audit memo (provider/tee_attested/attestation_id/model/prompt_hash/ts). The deterministic Jinja fallback lives in ML; your route must never break if the LLM is down. |
| **PII tokenization + re-id vault** | **YOU (BACKEND)** own the tokenization service + vault (request path); **PLATFORM** owns the HMAC key/secrets + egress controls | You implement HMAC-SHA256 tokenization + the local token↔real vault + audited unmask; PLATFORM custodies the key (Vault) and enforces egress. |
| **Reporting (FMR/CRILC/EWS/RFA)** | **YOU (BACKEND)** own the generators; **FRONTEND** owns the export UI; **DATABASE** stores outputs | You generate; FRONTEND renders/exports; DATABASE persists. |
| **Audit / WORM** | **DATABASE** owns the immutable/WORM store; **YOU write audit events** | Every action (incl. investigators' — "watch the watchers") writes an audit event to DATABASE's WORM store. Stub an append-only writer until DATABASE is live. |
| **Source connectors** | **DATA** owns adapters/fixtures; **PLATFORM** owns integration runtime (api-gateway, schema-registry hosting) | Your SIEM integration + RBI-pipeline feed are scaffolds that bind to DATA's adapters and PLATFORM's gateway. |
| **Testing** | each laptop owns its unit/contract tests; **PLATFORM** owns the cross-workstream integration harness + CI | You own `backend/tests/`; you contribute your contract tests to PLATFORM's harness. |

---

## 6. Your complete task list (every task, grouped by milestone)

Columns: **ID · what · deliverable path · status · blueprint ref · acceptance check.** Every inventory item maps into a task below. Keep the `TODO.md` rows in sync.

### M1 — API Foundations & Identity

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **BACKEND-1** | FastAPI app skeleton; `/api/v1` base path; JSON-over-HTTPS + mTLS-internal config; `GET /health`, `GET /metrics` (Prometheus); settings/config module; structured logging | `backend/services/api/app/main.py`, `app/config.py`, `app/observability/` | REAL | Part 24.2 (l.890–891, 915) | `GET /health` returns 200; `GET /metrics` exposes Prometheus text; all routes mounted under `/api/v1`; mTLS-internal flag present. |
| **BACKEND-2** | Keycloak OIDC auth + short-lived JWT issue/refresh; JWT-validation middleware on **all** routes | `backend/services/api/app/auth/oidc.py`, `app/routes/auth_routes.py` (`POST /auth/login`, `POST /auth/refresh`) | REAL | Part 24.1 (l.875), 24.2 (l.895) | Login does OIDC token exchange; refresh rotates; every non-public route 401s without a valid JWT; tokens short-lived. |
| **BACKEND-3** | RBAC permission matrix (**8 roles × 9 capabilities**) enforced per API call + OPA policy bundle + **SoD enforcement engine** | `backend/services/api/app/auth/rbac.py`, `app/auth/sod.py`, `app/auth/opa/` | REAL | Part 24.1 (l.877–888), 19.6 (l.651) | The full matrix (§7) is encoded; each route checks min-role; SoD rules block deployer labelling/closing own alerts and investigator tuning own-alert rules; PII-unmask is a **separate** audited capability. |
| **BACKEND-4** | Canonical API & payload contracts (Pydantic + OpenAPI): alert schema + disposition request/response | `backend/services/api/app/schemas/*.py`; generated `backend/openapi.json` | REAL | Part 24.5(b)(c) (l.978–1014) | Pydantic models match the sample alert (alert_id, entity_id, risk_score, severity, confidence, status, contributing_layers, reason_codes, exposure_inr, sla_due_ts, pii_tokenized) and disposition response (label_written, feedback_queued_for_retraining, audit_id); OpenAPI generates and is mirrored to `BACKEND.md §2/§3/§5`. |

### M2 — L1 Rules / BRE & SoD Matrix Engine

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **BACKEND-5** | **L1 Rules / Business-Rules Engine** (deterministic thresholds) — necessary-but-insufficient Layer 1; hot-reloadable; every rule versioned; **all named rules** | `backend/rules_engine/` (Flink-CEP/Drools-style + Python evaluator), `rules_engine/rules/*.yaml` | REAL | Part 3.1 (l.74–76), 20.1 (l.670–676) | Engine evaluates an L0 event and fires the named rules (§7): SWIFT↔CBS mismatch, new-beneficiary→high-value, dormant-reactivation→drain, DB-write-without-app-txn, entitlement self-grant, off-hours, just-under-threshold, etc.; rules are versioned + hot-reloadable; cold-start (no labels) works. |
| **BACKEND-6** | **SoD / toxic-combination matrix scoring engine** + OPA entitlement logic; emits toxic-combination flags | `backend/rules_engine/sod_matrix.py`, `rules_engine/opa/entitlement.rego` | REAL | Part 3.4 (l.90–96), Part 0/8 | Scores an event against the configurable SoD matrix; flags maker+checker-same-actor, create+approve, self-grant entitlement etc.; OPA evaluates least-privilege/entitlement logic. |
| **BACKEND-7** | Privileged-session & entitlement-change rule logic | `backend/rules_engine/privileged.py` | REAL | Part 2 (l.63), 19.3 (l.363) | Detects privileged-session correlation, **DB-write-without-app-transaction**, entitlement-change/self-grant, least-privilege violations, dormant-reactivation, orphaned-account use. |
| **BACKEND-8** | Change-controlled rule/threshold CRUD with **four-eyes** approval + audit | `backend/services/api/app/routes/rules_routes.py` (`GET/POST/PUT /rules`) | REAL | Part 24.2 (l.908), 31.3 (l.1282) | `/rules` CRUD restricted to Compliance; every change requires a second approver (four-eyes), is versioned, and writes an audit event. |

### M3 — Online Inference, Risk Fusion & Model Serving

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **BACKEND-9** | Model-serving layer (ONNX Runtime / Triton) scoring L2 unsupervised + L3 GBDT (+L4 session) inline; **model_version recorded on every score** | `backend/serving/` | REAL | Part 18.1/18.3 (l.569, 603) | Serves ONNX artifacts on port 8001; returns per-layer 0–1 scores; persists `model_version` with each score. (Stub artifacts until ML delivers.) |
| **BACKEND-10** | **Rust hot-path service tier** — ingestion/enrichment gateway, rules/scoring gateway, online inference service (`ort`/`candle`) | `backend/gateway/` (Rust crates) | REAL | Part 8 (l.314–315), 18.1 | Rust gateway ingests events, reads Redis/Feast features, calls rules + serving, runs inline inference; latency within budget (§8). |
| **BACKEND-11** | **L1 rules gateway hard-hit short-circuit** — emit HIGH alert immediately, skip ML | `backend/gateway/src/l1_shortcircuit.rs` | REAL | Part 18.1 (l.566) | On a hard rule hit the gateway emits a HIGH alert to the alerts topic immediately without invoking model serving. |
| **BACKEND-12** | **L6 risk-fusion service** — calibrated 0–100 + severity×confidence + reason codes via inline (non-interaction) **TreeSHAP**; rule-provenance/graph assembly | `backend/fusion/service.py` | REAL | Part 18.1 (l.572, 585) | Produces calibrated 0–100, severity×confidence, and assembled reason codes (rule provenance + SHAP top features + graph evidence) matching the alert schema; uses plain TreeSHAP (no interaction values inline). |
| **BACKEND-13** | End-to-end online inference topology wiring | `backend/deploy/` compose/k8s fragment for `backend/` services | REAL | Part 18.1 (l.557–578) | Wires Kafka(events)→Flink enrich+window→Redis/Feast→L1 gateway→model-serving→L6 fusion→Kafka(alerts)/ClickHouse/feature-snapshot, with async graph-update path; the worked burst (24.5d) replays to an alert. |
| **BACKEND-14** | **Idempotency / exactly-once & reliability patterns** | `backend/gateway/`, `backend/services/` reliability modules | REAL | Part 18.1 (l.590), 32.2 (l.1305) | Deterministic `event_id` keying + Flink checkpointing + Kafka transactions prevent double-alerts on replay; dedupe, retries-with-backoff, DLQ, circuit breakers, bulkheads, backpressure present. |
| **BACKEND-15** | **Graceful degradation to L1-rules-only** | `backend/gateway/src/degradation.rs` (+ Python fallback) | REAL | Part 18.1 (l.591), 30.1 (l.1240) | When model server is unavailable the path falls back to L1 rules only, never goes dark, and marks events for re-scoring. |
| **BACKEND-16** | Registry-driven artifact load + signature verify + canary hot-swap | `backend/serving/loader.py` | REAL | Part 23.4 (l.867–868), 18.3 | Loader pulls the Production artifact from the registry, **verifies signature**, hot-swaps via canary, records model version on every score; rejects unsigned/invalid artifacts. |

### M4 — API Surface, PII Tokenization & EDD Feedback

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **BACKEND-17** | **PII tokenization layer + local re-identification vault** | `backend/services/api/app/pii/tokenizer.py`, `app/pii/vault.py` | REAL | Part 25.3/25.5 (l.1041–1045, 1061), 24.1 (l.875, 907) | Deterministic keyed `HMAC-SHA256(secret, value)` truncated to readable tokens (`EMP-7f3a`, `ACCT-4d22`, `BEN-9b1c`) runs **before egress**; token↔real mapping in a local vault; `POST /entities/{id}/unmask` de-tokenizes for authorized (Senior+) users and writes an audit event. |
| **BACKEND-18** | Field-level PII encryption + at-rest/in-transit protection | `backend/services/api/app/pii/crypto.py` | REAL | Part 19.3 (l.363, 633) | Field-level encryption/tokenization/masking of PII/PAN; mTLS in transit; at-rest encryption wired to KMS/HSM keys (PLATFORM-custodied). |
| **BACKEND-19** | Alert routes + queue + entity-360 + explanations | `backend/services/api/app/routes/alert_routes.py`, `entity_routes.py`, `explanation_routes.py` | REAL | Part 24.2 (l.896–905), Part 11 (l.382–391) | `GET /alerts` (filtered/paginated, ranked by fused risk×exposure×confidence, deduped per entity), `GET /alerts/{id}`, `GET /entities/{id}` + `/timeline` + `/graph` + `/peers`, `GET /explanations/{alert_id}` returning **SHAP + rule provenance + sequence attention**. |
| **BACKEND-20** | **EDD disposition + feedback write path** (human-in-the-loop, alert-only) | `backend/services/api/app/routes/disposition_routes.py`, `feedback_routes.py` | REAL | Part 24.2 (l.898–900, 911), 16 (l.500), 19.6/29.2 (l.651, 1223) | `POST /alerts/{id}/assign`, `POST /alerts/{id}/disposition` (writes label, returns `label_written`+`feedback_queued_for_retraining`+`audit_id`, **queues label to ML feedback loop / DATA label-source-4**), `POST /feedback`, `POST /alerts/{id}/block-request` (Analyst→Lead approves, **never auto**); a mandatory human decision precedes any classification. |
| **BACKEND-21** | Model, drift & metrics routes (registry-driven) | `backend/services/api/app/routes/model_routes.py` | REAL | Part 24.2 (l.909–910) | `GET /models`, `POST /models/{id}/promote` (Model-Eng + sign-off, SoD-checked), `GET /drift`, `GET /metrics/model`. |
| **BACKEND-22** | Audit, admin, RBAC-scoped case access + watch-the-watchers | `backend/services/api/app/routes/audit_routes.py`, `admin_routes.py`; `app/auth/case_scope.py` | REAL | Part 24.2 (l.913–914), 19.3 (l.635), 29.2 (l.1227) | `GET /audit` (immutable trail incl. **who-viewed-whom**, Auditor role), `GET/POST /admin/users` (Platform Admin), analysts see only **assigned** cases, session controls, **every view/action logged** (investigators audited + subject to fairness review). |
| **BACKEND-23** | Severity-based escalation routing + SLA/TAT timers | `backend/services/api/app/workflow/escalation.py` | REAL | Part 33.3 (l.1333–1334), Part 11 (l.387) | Severity-based routing; SLA/TAT timers (**RBI ≤30-day**); populates `sla_due_ts` on every alert. |

### M5 — Regulatory Generators, External Integration & Edge

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **BACKEND-24** | **EWS / RFA / CRILC / FMR / CFR** regulatory generators | `backend/regulatory/` (`ews.py`, `rfa.py`, `crilc.py`, `fmr.py`, `cfr.py`) | SCAFFOLD | Part 16 (l.496–503) | EWS-framework integration with CBS; RFA tagging; **CRILC ₹3-crore/7-day + 180-day** window logic; FMR generation; CFR feed; DAMI-unit support. SCAFFOLD because the live RBI submission channel doesn't exist; logic runs on synthetic data. |
| **BACKEND-25** | Slow-lane entity/credit scoring (named Part-12 typologies) + RBI EWS/CRILC pipeline feed | `backend/regulatory/slow_lane.py` | SCAFFOLD | Part 18.2 (l.599), 13 (l.452–453), **Part 12 coverage map (l.415–419)** | Daily/weekly batch entity/credit scoring for red-flagged accounts feeding the EWS/CRILC pipeline. **Must score the four named slow-lane typologies, not a generic scorer:** (a) **fake-vendor/billing** (vendor-address=employee-address, single-client vendor, round/sequential invoices), (b) **ghost-employees/payroll** (no-tax-footprint, duplicated bank details), (c) **alert-suppression by AML watchers** (per-analyst disproportionate clear-rate, reopened-then-cleared), (d) **ghost/insider-loans+inflated-appraisal** (thin docs, appraiser-is-borrower, disbursement-to-non-sanctioned-account) — consuming the DATA slow-lane features (DATA-20/21) and the `lane:slow` simulator traces (DATA-9). Emits RFA tags + EWS indicators. SCAFFOLD only because the live RBI submission channel doesn't exist; the typology scoring runs REAL on synthetic data. |
| **BACKEND-26** | Regulatory export routes (FMR/CRILC) | `backend/services/api/app/routes/report_routes.py` (`GET /reports/fmr`, `GET /reports/crilc`) | REAL | Part 24.2 (l.912) | Produce CRILC/FMR-ready exports; Compliance-only; consumed by FRONTEND, stored by DATABASE. |
| **BACKEND-27** | Bi-directional SIEM integration (consume logs / publish alerts) | `backend/integrations/siem.py` | SCAFFOLD | Part 9.3 (l.366) | Consumes SIEM logs as a source and publishes alerts as a sink; scaffolded against the bank's live SIEM. |
| **BACKEND-28** | API gateway front (auth, rate-limit, routing, observability) | `backend/gateway_config/` (Kong/APISIX config) | REAL | Part 32.1 (l.1301) | Gateway fronts app APIs with auth, rate-limiting, routing, observability (PLATFORM hosts the runtime). |
| **BACKEND-29** | Cross-border / DPDP transfer controls & data-principal rights | `backend/compliance/` | SCAFFOLD | Part 28.1 (l.1196–1198) | PII tokenized before egress with TEE-attestation note; transfer documentation + destination-jurisdiction confirmation; data-principal access/correction/erasure/grievance handling with response SLAs. SCAFFOLD because TEE hardware + legal jurisdiction confirmation are external. |

---

## 7. Detailed build instructions per milestone (blueprint specifics — spelled out)

### 7.1 RBAC matrix (BACKEND-3) — encode EXACTLY (Part 24.1)

**8 roles × 9 capabilities.** ✅ = allowed; ⚠️ = conditional; ❌ = denied.

| Role ↓ / Capability → | View alerts | Triage/assign | Disposition | Request block | Unmask PII | Tune rules | Train/deploy models | View audit | Admin |
|---|---|---|---|---|---|---|---|---|---|
| **Analyst (L1)** | ✅ assigned only | ✅ | ✅ | ✅ request | ⚠️ case-scoped, logged | ❌ | ❌ | ❌ | ❌ |
| **Senior Investigator** | ✅ all | ✅ | ✅ | ✅ | ✅ logged | ❌ | ❌ | view own | ❌ |
| **Team Lead / MLRO** | ✅ | ✅ | ✅ override | ✅ approve | ✅ logged | ⚠️ propose | ❌ | ✅ | ❌ |
| **Compliance Officer** | ✅ | ❌ | ❌ | ❌ | ✅ logged | ✅ change-controlled | ❌ | ✅ | ❌ |
| **Auditor** | ✅ read-only | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ full | ❌ |
| **Model Engineer / Data Scientist** | ⚠️ de-identified only | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ with sign-off | view own | ❌ |
| **Platform Admin** | ❌ no case data | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ deploy infra | ✅ | ✅ |
| **Service accounts** | scoped tokens | — | — | — | ❌ | ❌ | ❌ | write-only | ❌ |

**SoD rule (Part 19.6 — enforce in `sod.py`):** whoever **deploys models** cannot **label data** or **close their own alerts**; whoever **investigates** cannot **tune the rules** that generate their alerts unchecked. PII unmask is a **separate, audited** permission. Analyst case-scoping = sees only assigned cases. Model Engineer sees **de-identified** data only. Promotion requires sign-off (second person ≠ the engineer).

### 7.2 L1 rules / BRE + SoD (BACKEND-5/6/7) — named rules (Part 20.1, 24.5)

Implement at minimum these **named deterministic rules**, each versioned, hot-reloadable, with provenance code emitted into reason_codes:
- **`SWIFT_CBS_MISMATCH`** — SWIFT message without matching CBS transaction (the PNB control; linkage key joins SWIFT↔CBS).
- **`NEW_BENEFICIARY_THEN_HIGHVALUE`** — new beneficiary created then high-value payment within a short latency window (the 24.5d worked burst).
- **`DORMANT_REACTIVATION_DRAIN`** — dormant account reactivated then drained.
- **`DB_WRITE_WITHOUT_APP_TXN`** — direct DB write with no corresponding application transaction (linkage app-txn↔DB-write).
- **`ENTITLEMENT_SELF_GRANT`** — actor grants themselves an entitlement / privilege escalation.
- **`OFF_HOURS_ACTIVITY`** — activity outside the actor's + peer baseline hours (`is_off_hours`).
- **`JUST_UNDER_THRESHOLD`** — amount structured just below a reporting/approval threshold.
- **SoD/toxic-combination** — same actor as maker AND checker; create-beneficiary + approve-payment by the same maker-checker pair; toxic entitlement combinations scored against the configurable SoD matrix.
- **Privileged** — privileged-session correlation, orphaned-account use, no-leave streak / leaver-window exfil proxies.

Each rule reads L0 event fields + Redis/Feast online features (consume from DATA; stub until live). Hard-hit rules feed the **L1 short-circuit** (BACKEND-11). Rule/threshold changes are **four-eyes + audited** (BACKEND-8, Part 31.3).

### 7.3 Online inference + fusion (BACKEND-9..16) — Part 18 specifics

- **Topology (18.1):** `Kafka(events) → Flink(enrich+window) → Redis/Feast → L1 rules gateway → model-serving(L2+L3 +L4 if window mature) → L6 fusion → Kafka(alerts) + ClickHouse + feature-snapshot`; async `entity/edge → graph store → L5` may **upgrade** an existing alert (never blocks the hot path).
- **Trees in the hot path, deep nets out of it.** L2/L3 score inline; L4 sequence + L5 graph run on session-close / short async cadence.
- **Latency budget (alert-only, not in the payment path; target end-to-end ≤ ~100–300 ms):** Kafka+Flink ~10–40 ms · Redis lookup ~1–5 ms · L1 rules <5 ms · L2+L3 ONNX ~5–30 ms · **TreeSHAP (plain, not interaction values) ~5–20 ms** · fusion+emit ~5–10 ms.
- **L6 fusion output:** calibrated **0–100** risk score + **severity×confidence** + assembled **reason codes** (rule provenance + SHAP top features + graph evidence) exactly matching the alert schema.
- **Idempotency/exactly-once (18.1):** deterministic `event_id` keying + Flink checkpointing + Kafka transactions; a replay must not double-alert.
- **Graceful degradation (18.1, 30.1):** model server down → **L1 rules only**, mark events for re-scoring; never go dark.
- **Caching:** per-entity baselines + peer-group stats in Redis with TTL; recompute on schedule, not per event.
- **Serving load (23.4):** pull Production artifact, **verify signature**, canary hot-swap, record model version on every score.

### 7.4 Alert schema (BACKEND-4/12/19) — match Part 24.5(b) exactly

Fields: `alert_id` (`alr_*`), `entity_id` (=`employee_id`, e.g. `EMP-7f3a`), `risk_score` (0–100 int), `severity` (low/medium/high), `confidence` (0–1 float), `status`, `created_ts` (UTC ISO-8601 `…Z`), `contributing_layers` (list of `L1_rules`/`L2_unsupervised`/`L3_gbdt`/`L4_sequence`/`L5_graph`), `reason_codes` (list of `{source: rule|shap|graph, ...}`), `exposure_inr` (int minor units / INR), `sla_due_ts`, `pii_tokenized` (bool). Mirror to `BACKEND.md §2`.

### 7.5 Disposition contract (BACKEND-20) — match Part 24.5(c) exactly

`POST /api/v1/alerts/{id}/disposition` body `{ outcome: fraud|false_positive|inconclusive, notes, evidence_ids[] }` → `200` `{ alert_id, status, label_written: true, feedback_queued_for_retraining: true, audit_id }`. The disposition **writes a label** to the labeled store (DATA label-source-4 / ML feedback loop) and an audit event. Alert-only: never auto-classify; the human disposition is the classification.

### 7.6 PII tokenization + vault (BACKEND-17/18) — Part 25.3/25.5

`tok(value) = HMAC-SHA256(secret_key, value)` truncated to a readable token with a type prefix (`EMP-…`, `ACCT-…`, `BEN-…`). Tokenization runs **before any egress** (esp. before the narrative LLM call). The **token↔real mapping lives only in a local re-id vault** (Postgres, encrypted) and is **never sent out**. `POST /entities/{id}/unmask` de-tokenizes on display for authorized (Senior+, case-scoped/logged for Analyst) users and writes an audit event. The HMAC key is custodied by PLATFORM (Vault); you read it from the secret, never hardcode it.

### 7.7 Narrative route (BACKEND-20-adjacent / contract) — Part 25.4

`POST /narratives/{alert_id}` (Analyst+) assembles **tokenized** alert context and calls **ML's `narrate()`** gateway (NEAR AI primary → Groq secondary → deterministic Jinja template — **UI never breaks**). Persist the **audit memo**: `provider` (`near_ai`/`groq`/`template`), `tee_attested` (bool), `attestation_id`, `model`, `prompt_hash`, `ts`. ML owns the gateway/fallback; PLATFORM owns egress + secrets + the TEE-attestation MOCK; you own the route + audit-memo write. Mirror columns to `BACKEND.md §7`.

### 7.8 Regulatory generators (BACKEND-24/25/26) — Part 16

EWS framework integrated with CBS; **RFA** (Red-Flagged Account) tagging; **CRILC**: ₹3-crore exposure / 7-day reporting trigger + **180-day** classification window; **FMR** (Fraud Monitoring Returns) generation; **CFR** (Central Fraud Registry) feed; **DAMI** (Data Analytics & Market Intelligence) unit support; slow-lane entity/credit scoring feeds the pipeline. SCAFFOLD against the live regulator channel; logic runs fully on synthetic data. Alert-only / natural justice (Part 16, 29.2): the system flags + evidences, never auto-classifies.

### 7.9 Audit + escalation + DPDP (BACKEND-22/23/29)

- **Audit-write of EVERY action** to the DATABASE WORM store: alert views (who-viewed-whom), assignments, dispositions, unmasks, rule changes, model promotions, admin changes, narrative generations. Investigators' actions are audited and subject to fairness review ("watch the watchers", Part 29.2).
- **Escalation/SLA (Part 33.3):** severity-based routing + SLA/TAT timers, RBI ≤30-day, populate `sla_due_ts`.
- **DPDP/cross-border (Part 28.1):** data-principal access/correction/erasure/grievance with response SLAs; PII tokenized before egress; transfer documentation + destination-jurisdiction note.

---

## 8. Testing & all checks (commands + what must pass)

Run all of these green before any milestone is "done."

**Python (in `backend/`):**
```
ruff check . && black --check . && mypy .
pytest -q                       # unit + integration + contract
pytest -q tests/contract        # API contract tests (httpx against the app)
```
**Rust (in `backend/gateway/`):**
```
cargo fmt --check && cargo clippy -- -D warnings && cargo test
```

**Required test coverage (what must pass):**
- **Setup/deps:** versions pinned to Part 24.3 in `pyproject.toml`/`Cargo.toml`; lockfiles committed.
- **Lint/format/type:** ruff + black + mypy clean (Python); rustfmt + clippy `-D warnings` clean (Rust).
- **Unit tests:** each rule fires/does-not-fire on crafted L0 events; SoD matrix combinations; tokenizer determinism + truncation format; RBAC allow/deny per (role×capability); SoD-deny cases; escalation/SLA computation; CRILC ₹3-crore/7-day + 180-day window logic; fusion calibration to 0–100.
- **Integration tests:** the **24.5(d) worked burst** replays end-to-end (create_beneficiary off-hours → approve_payment high-value → graph ring → L6 risk ~high → alert emitted with assembled reason codes). Graceful-degradation test: model server down → L1-rules-only alert + event marked for re-scoring. Idempotency test: replay same `event_id` → no double alert.
- **Contract tests:** every route in §6 returns the schema in `BACKEND.md`; disposition returns the exact 24.5(c) response; alert matches 24.5(b); `/health` + `/metrics` shape.
- **Security checks:** `pip-audit`/`cargo audit` for CVEs; no hardcoded secrets (HMAC key from Vault); every non-public route rejects missing/invalid JWT; unmask + every action writes an audit event; PII tokenized before egress (assert no raw PII leaves the perimeter in the narrative path).
- **Domain checks:** alert-only invariant (no code path auto-blocks or auto-classifies; block-request requires Lead approval); "watch-the-watchers" audit on investigator actions; four-eyes on rule changes.
- **Performance/latency budget (Part 18.1):** a latency test asserts the online decision path stays within the per-stage budget (rules <5 ms, L2+L3 ~5–30 ms, TreeSHAP ~5–20 ms, end-to-end ≤ ~300 ms on the test rig).

**Definition of Done per milestone:** all tasks in the milestone `[x]`; blueprint refs validated and logged; all checks above green; `BACKEND.md` + `TODO.md` + your laptop log updated; relevant `CONTEXT.md` entries appended; contract tests contributed to PLATFORM's harness.

---

## 9. Blueprint validation gate (each owned requirement → covered)

Mark each ✅ in your laptop log when validated against the cited Part.

- [ ] Part 24.2 — **every** API route built (auth, alerts, entities×4, explanations, narratives, unmask, rules, models×2, drift/metrics, feedback, reports×2, audit, admin×2, health/metrics) → BACKEND-1,2,4,8,19,20,21,22,26 + narrative route.
- [ ] Part 24.1 — **8-role × 9-capability RBAC** + SoD rule + separate audited unmask → BACKEND-3.
- [ ] Part 3.1 / 20.1 — L1 rules/BRE deterministic baseline, all named rules, versioned/hot-reloadable → BACKEND-5.
- [ ] Part 3.4 / 0 — SoD/toxic-combination matrix scoring + OPA entitlement → BACKEND-6.
- [ ] Part 2 / 19.3 — privileged-session, DB-write-without-app-txn, entitlement self-grant → BACKEND-7.
- [ ] Part 31.3 — four-eyes change-controlled rule CRUD → BACKEND-8.
- [ ] Part 18.1/18.3/23.4 — online topology, model serving, L1 short-circuit, L6 fusion + TreeSHAP reason codes, idempotency/exactly-once, graceful degradation, registry-driven signed load + canary, latency budget → BACKEND-9..16.
- [ ] Part 25.3/25.5 — HMAC-SHA256 tokenization + re-id vault + audited unmask + before-egress → BACKEND-17,18.
- [ ] Part 11 / 24.4 — triage ranking, entity-360 timeline, explanation (SHAP+rule+attention), graph, peers data → BACKEND-19.
- [ ] Part 16 / 19.6 / 29.2 — EDD disposition→label feedback loop, alert-only, human-in-the-loop, block-request never auto → BACKEND-20.
- [ ] Part 24.2 — model/drift/metrics routes → BACKEND-21.
- [ ] Part 19.3 / 29.2 — audit-write of every action, who-viewed-whom, case-scope, watch-the-watchers → BACKEND-22.
- [ ] Part 33.3 — severity escalation + SLA/TAT (RBI ≤30-day) + sla_due_ts → BACKEND-23.
- [ ] Part 16 — EWS/RFA/CRILC(₹3cr/7d/180d)/FMR/CFR/DAMI generators + slow-lane feed + export routes → BACKEND-24,25,26.
- [ ] Part 9.3 — bi-directional SIEM integration → BACKEND-27.
- [ ] Part 32.1 — API gateway front → BACKEND-28.
- [ ] Part 28.1 — DPDP cross-border controls + data-principal rights → BACKEND-29.
- [ ] Part 24.5(b)(c) — alert + disposition payload contracts exact → BACKEND-4.

If any box can't be ticked, do NOT mark the task done; log the gap in `CONTEXT.md`.

---

## 10. Definition of Done & handoff

A milestone (and ultimately the workstream) is **done** when:
1. Every task is `[x]` in `TODO.md`, blueprint-validated with the Part cited.
2. All §8 checks pass (lint/format/type, unit/integration/contract, security, domain, latency).
3. **`BACKEND.md` is fully synced** with the implemented API, alert schema, RBAC matrix + SoD rule, disposition contract, model-serving interface, narrative audit columns, and pinned versions — because every other laptop integrates against it.
4. Your laptop log `docs/laptops/03-backend.md` records decisions, files, blueprint validations, deviations, blockers, and every stub created for not-yet-built dependencies.
5. `CONTEXT.md` integration log has your cross-cutting decisions (newest first), and any cross-laptop blocker is in `TODO.md §7` + mirrored to `CONTEXT.md`.
6. **Integration test with other parts:** the worked-burst end-to-end (DATA event stream → your L1 rules → ML L2/L3 + L6 fusion → your alert API → FRONTEND queue), disposition→label loop into ML/DATA, audit-write into DATABASE's WORM store, narrative route into ML's gateway, and registry-driven signed load from DATABASE+ML registry — all verified or stubbed-with-contract-honored. Contract tests contributed to PLATFORM's cross-workstream harness.

**Golden rules at handoff (restate):** ALERT-ONLY (never auto-block, never auto-classify) · ON-PREM + SYNTHETIC only · validate-against-blueprint (cite the Part) · nothing-dropped · stay-in-lane (only `backend/` + `BACKEND.md` + own log + append shared MD).
