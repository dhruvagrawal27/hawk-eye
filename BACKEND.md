# BACKEND.md — Integration Contract (owned by the BACKEND laptop)

> **This is the contract every laptop integrates against.** BACKEND owns and updates it; **everyone else reads it**. If you (non-BACKEND) need a change, propose it in `CONTEXT.md` and tag BACKEND. Kept in sync with the real implementation in `backend/`. Validated against blueprint **Parts 11, 16, 18, 24, 25** (and 5.1 for the event model). **ALERT-ONLY**: the system scores, explains, and *requests* a block; a human decides — it never auto-blocks money and never auto-classifies fraud.

## 0. Pinned versions (blueprint Part 24.3 — verify latest patch before locking)
Kafka 3.8.x · Flink 1.20.x · ClickHouse 25.x · Redis 7.4.x · Feast 0.40.x · PostgreSQL 17.x · Python 3.12.x · LightGBM/XGBoost/CatBoost 4.5/2.1/1.2 · PyTorch/PyG 2.5/2.6 · PyOD/scikit-learn 2.0/1.6 · ONNX Runtime/Triton 1.20/25.x · FastAPI/Uvicorn 0.115/0.32 · Pydantic 2.x · Authlib (JWT) 1.3+ · React/TS/Node 19/5.6/22 · MLflow 2.18 · Airflow 2.10 · Drools/OPA 8.x · Keycloak 25.x · Evidently 0.4.x · Prometheus/Grafana 3/11 · Docker/K8s 27/1.31 · Rust stable + `ort`→ONNX 1.20 · OpenAI SDK 1.5x · Terraform 1.9.
> Backend lockfiles: `backend/pyproject.toml` (Python), `backend/gateway/Cargo.toml` (Rust). Local dev validated on Python 3.13 / FastAPI 0.135 (a newer patch than the pins); CI pins the blueprint versions.

## 1. L0 Unified Event (input to the pipeline) — DATA owns the schema, BACKEND consumes
```json
{
  "event_id": "evt_8f2a1c90",
  "ts": "2026-06-30T02:14:07Z",
  "actor":  { "employee_id": "EMP-7f3a", "role": "ops_maker", "dept": "trade_finance",
              "branch": "BR-219", "tenure_days": 2840, "peer_group": "PG-ops-tf",
              "privileged_flag": false, "leaver_flag": false },
  "action": { "verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker" },
  "object": { "beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": null, "currency": "INR" },
  "context":{ "src_ip": "10.20.4.31", "device": "WS-114", "geo": "Mumbai",
              "session_id": "sess_55e1", "layer": "application", "is_off_hours": true },
  "linkage":{ "swift_ref": null, "cbs_txn_id": null, "app_txn_id": null, "db_write_id": null,
              "related_event_id": null, "customer_account_id": null }
}
```
Field groups (blueprint 5.1): **Actor / Action / Object / Context / Linkage** (linkage = correlation keys joining SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account). BACKEND parses this additively (`extra=allow`); if you need a field, propose in `CONTEXT.md` and tag DATA.

### 1a. Online feature keys BACKEND reads (DATA materializes in Feast/Redis)
The rules engine + fusion read these online features by Feast key (consume from DATA; BACKEND stubs them until live):
`is_off_hours` · `minutes_since_new_beneficiary` · `beneficiary_age_days` · `beneficiary_created_by` · `maker_checker_same_actor` · `maker_checker_pair_isolated` · `maker_checker_partner` · `account_dormant_days` · `account_recently_reactivated` · `amount_zscore` · `swift_without_cbs_match` · `privileged_session` · `least_privilege_violation` · `account_orphaned` · `in_leaver_window` · `export_record_count` · `no_leave_days` · `held_entitlements[]` · `is_self_grant`.

## 2. L6 Alert (output of fusion) — BACKEND owns
```json
{
  "alert_id": "alr_3d7e22", "entity_id": "EMP-7f3a",
  "risk_score": 87, "severity": "high", "confidence": 0.82, "status": "open",
  "created_ts": "2026-06-30T02:41:55Z",
  "contributing_layers": ["L1_rules","L2_unsupervised","L3_gbdt","L5_graph"],
  "reason_codes": [
    { "source":"rule",  "code":"NEW_BENEFICIARY_THEN_HIGHVALUE", "detail":"new payee BEN-9b1c paid INR 48,00,000 within 27 min" },
    { "source":"shap",  "feature":"new_beneficiary_to_payment_latency_min", "contribution":0.31 },
    { "source":"graph", "detail":"maker EMP-7f3a + checker EMP-1a09 recur as isolated pair (ring RNG-12)" }
  ],
  "exposure_inr": 4800000, "sla_due_ts": "2026-07-30T02:41:55Z", "pii_tokenized": true
}
```
- `risk_score` 0–100 int · `severity` low|medium|high · `confidence` 0–1 · `status` ∈ {open, assigned, in_review, block_requested, confirmed_fraud, false_positive, inconclusive, closed} · `created_ts`/`sla_due_ts` UTC ISO-8601 `…Z` · `reason_codes[].source` ∈ {rule, shap, graph, sequence} · `sla_due_ts` = created + RBI ≤30-day cap · `pii_tokenized` always `true` on egress (raw PII never in an alert).

## 3. API (base `/api/v1`, JWT required, RBAC = minimum capability) — blueprint Part 24.2
| Method & path | Purpose | Min capability / role |
|---|---|---|
| `POST /auth/login`, `POST /auth/refresh` | OIDC token exchange/refresh (short-lived JWT, refresh rotates) | public |
| `GET /alerts?status=&risk_gte=&assignee=&limit=&offset=` | Ranked (risk×exposure×confidence), deduped-per-entity, case-scoped queue | view_alerts |
| `GET /alerts/{id}` | Full alert (audited who-viewed-whom) | view_alerts |
| `POST /alerts/{id}/assign` | Assign/claim | triage_assign |
| `POST /alerts/{id}/disposition` | EDD outcome → **label** (§5) | disposition |
| `POST /alerts/{id}/block-request` | Raise block **request** (never auto; Lead approves) | request_block |
| `GET /entities/{id}` `/timeline` `/graph` `/peers` | Entity-360 (audited) | view_alerts |
| `POST /entities/{id}/unmask` | Re-identify tokenized PII (audited; Analyst needs justification) | unmask_pii |
| `GET /explanations/{alert_id}` | SHAP + rule provenance + sequence attention + graph | view_alerts |
| `POST /narratives/{alert_id}` | TEE-LLM narrative + audit memo (§7) | view_alerts |
| `GET /rules` · `POST /rules` · `POST /rules/{change_id}/approve` | Change-controlled CRUD + **four-eyes** (§6 below) | tune_rules |
| `GET /models` · `POST /models/{id}/promote?version=` | Registry view / promotion (signed, SoD sign-off) | train_deploy_models |
| `GET /drift?model_id=` · `GET /metrics/model?model_id=` | Drift & model quality | train_deploy_models |
| `POST /feedback` | Active-learning label submission | disposition |
| `GET /reports/fmr` · `GET /reports/crilc` | Regulatory export (Compliance) | role: compliance/lead |
| `GET /audit?actor=&entity=&action=` | Immutable trail incl. who-viewed-whom | view_audit |
| `GET /admin/users` · `POST /admin/users` | User/role mgmt | admin |
| `POST /compliance/transfers` · `POST /compliance/data-principal` | DPDP transfer + data-principal rights (SCAFFOLD) | role: compliance/lead/admin |
| `POST /events/ingest?full=` | Synthetic L0 ingestion into the online topology (Kafka is the prod entry) | any authenticated |
| `GET /health` · `GET /metrics` | Liveness + Prometheus (root paths) | public |

OpenAPI is generated to `backend/openapi.json`.

## 4. RBAC — 8 roles × 9 capabilities (blueprint Part 24.1) + SoD
**Roles:** analyst · senior_investigator · team_lead (MLRO) · compliance_officer · auditor · model_engineer · platform_admin · service_account.
**Capabilities:** view_alerts · triage_assign · disposition · request_block · unmask_pii · tune_rules · train_deploy_models · view_audit · admin.
Matrix encoded exactly in `app/auth/rbac.py` (+ OPA bundle `app/auth/opa/rbac.rego`); ✅ allow / ⚠️ conditional / ❌ deny per Part 24.1.
**SoD rule (Part 19.6):** whoever **deploys models** cannot **label data** or **close their own alerts**; whoever **investigates** cannot **tune the rules** that generate their alerts unchecked. **PII unmask is a separate, audited capability.** Model promotion needs a second-person sign-off (promoter ≠ approver). Four-eyes on rule changes (proposer ≠ approver). Analyst = assigned cases only; Model Engineer = de-identified data only.

## 5. EDD disposition / feedback (request → response) — Part 24.5c
```http
POST /api/v1/alerts/alr_3d7e22/disposition
{ "outcome":"fraud", "notes":"Confirmed shell beneficiary; maker-checker collusion.", "evidence_ids":["evt_8f2a1c90"] }
```
```json
{ "alert_id":"alr_3d7e22","status":"confirmed_fraud","label_written":true,
  "feedback_queued_for_retraining":true,"audit_id":"aud_99f0c1" }
```
`outcome` ∈ {fraud, false_positive, inconclusive}. Writes a label to the labeled store (DATA label-source-4 / ML feedback loop) + an audit event. **Alert-only**: the human disposition *is* the classification. `block-request` → `{auto_blocked:false, requires_approval_by:"team_lead"}`.

## 6. L1 rules / SoD engine (BACKEND owns) — Part 20.1 / 3.4
Named, versioned, hot-reloadable, cold-start-safe rules (`rules_engine/rules/*.yaml`): `SWIFT_CBS_MISMATCH`, `NEW_BENEFICIARY_THEN_HIGHVALUE`, `DORMANT_REACTIVATION_DRAIN`, `DB_WRITE_WITHOUT_APP_TXN`, `ENTITLEMENT_SELF_GRANT`, `OFF_HOURS_ACTIVITY`, `JUST_UNDER_THRESHOLD`, plus privileged (`PRIVILEGED_SESSION_CORRELATION`, `ORPHANED_ACCOUNT_USE`, `LEAST_PRIVILEGE_VIOLATION`, `LEAVER_WINDOW_EXFIL`, `NO_LEAVE_STREAK`) and SoD flags (`SOD_MAKER_CHECKER_SAME_ACTOR`, `SOD_CREATE_APPROVE_ISOLATED_PAIR`, `SOD_SELF_GRANT_ENTITLEMENT`, `SOD_TOXIC_ENTITLEMENT_COMBINATION`). `hard_hit:true` rules feed the **L1 short-circuit** (emit HIGH immediately, skip ML). Thresholds live in YAML → changing one is a **four-eyes audited rule change**, not a code change.

## 6a. Model-serving interface (ML ↔ BACKEND) — Part 18
ONNX Runtime/Triton on **:8001**. `POST /score {feature_vector, layers?, window_mature?, routing_key?}` → `{scores:{L2_unsupervised, L3_gbdt[, L4_sequence]}, model_versions:{…}, degraded_layers:[]}`. Per-layer 0–1 scores; **`model_version` recorded on every score**. BACKEND fuses (L6) → calibrated 0–100 + severity×confidence + reason codes (plain inline TreeSHAP, no interaction values). Registry-driven signed load + canary hot-swap (`serving/loader.py`); unsigned/invalid artifacts are rejected. Graceful degradation: serving down ⇒ **L1-rules-only** + mark for re-score, never dark.

## 6b. Online topology + reliability — Part 18.1
`Kafka(events)→Flink enrich+window→Redis/Feast→L1 gateway→serving(L2+L3)→L6 fusion→Kafka(alerts)+ClickHouse`; async graph/L5 may upgrade an alert. Production hot path = Rust (`backend/gateway/`); Python reference = `app/pipeline/online.py`. Exactly-once via deterministic `event_id` keying (a replay never double-alerts); circuit breakers / retries-with-backoff / DLQ / degradation in `reliability/`.

## 7. Narrative LLM (BACKEND ↔ ML gateway) — Part 25
`POST /narratives/{alert_id}` → **tokenized** alert context → ML `narrate()` (NEAR AI primary → Groq secondary → **deterministic Jinja template** — UI never breaks). PII is HMAC-SHA256 tokenized **before egress** (`EMP-…`, `ACCT-…`, `BEN-…`; token↔real only in the local re-id vault). Every narrative writes an **audit memo**: `provider` (`near_ai`/`groq`/`template`), `tee_attested` (bool), `attestation_id`, `model`, `prompt_hash`, `ts`.

## 8. Regulatory generators (BACKEND owns; SCAFFOLD on live RBI channel) — Part 16
EWS (CBS-integrated indicators) · RFA tagging · CRILC **₹3-crore / 7-day + 180-day** window · FMR (from human-confirmed fraud only) · CFR feed · DAMI analytics · slow-lane scoring of the **four named typologies** (fake-vendor, ghost-employee, alert-suppression, ghost-loan). Logic runs REAL on synthetic data; only the live submission channel is absent.

---
*BACKEND laptop: keep this current with the real implementation. Others: integrate against this, do not guess.*
