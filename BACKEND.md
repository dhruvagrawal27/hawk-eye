# BACKEND.md — Integration Contract (owned by the BACKEND laptop)

> **This is the contract every laptop integrates against.** BACKEND owns and updates it; **everyone else reads it**. If you (non-BACKEND) need a change, propose it in `CONTEXT.md` and tag BACKEND. Keep this in sync with the implemented API. Validated against blueprint **Parts 11, 18, 24** (and 5.1 for the event model).

## 0. Pinned versions (blueprint Part 24.3 — verify latest patch before locking)
Kafka 3.8.x · Flink 1.20.x · ClickHouse 25.x · Redis 7.4.x · Feast 0.40.x · PostgreSQL 17.x · Python 3.12.x · LightGBM/XGBoost/CatBoost 4.5/2.1/1.2 · PyTorch/PyG 2.5/2.6 · PyOD/scikit-learn 2.0/1.6 · ONNX Runtime/Triton 1.20/25.x · FastAPI/Uvicorn 0.115/0.32 · React/TS/Node 19/5.6/22 · MLflow 2.18 · Airflow 2.10 · Drools/OPA 8.x · Keycloak 25.x · Evidently 0.4.x · Prometheus/Grafana 3/11 · Docker/K8s 27/1.31 · OpenAI SDK 1.5x · Terraform 1.9.

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
              "session_id": "sess_55e1", "layer": "application", "is_off_hours": true }
}
```
Field groups (blueprint 5.1): **Actor / Action / Object / Context / Linkage** (linkage = correlation keys joining SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account).

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

## 3. API (base `/api/v1`, JWT required, RBAC = minimum role) — blueprint Part 24.2
| Method & path | Purpose | RBAC |
|---|---|---|
| `POST /auth/login`, `POST /auth/refresh` | OIDC token exchange/refresh | public |
| `GET /alerts?status=&risk_gte=&assignee=` | Ranked alert queue (paginated) | Analyst |
| `GET /alerts/{id}` | Full alert (score, reason codes, contributing layers) | Analyst |
| `POST /alerts/{id}/assign` | Assign/claim | Analyst |
| `POST /alerts/{id}/disposition` | EDD outcome (`fraud`/`false_positive`/`inconclusive`) → **label** | Analyst |
| `POST /alerts/{id}/block-request` | Raise block request (human action, never auto) | Analyst→Lead |
| `GET /entities/{id}` | Entity-360 profile + risk | Analyst |
| `GET /entities/{id}/timeline` | Unified txn+access+data+change timeline | Analyst |
| `GET /entities/{id}/graph` | Relationship/collusion subgraph | Analyst |
| `GET /entities/{id}/peers` | Peer-group comparison | Analyst |
| `GET /explanations/{alert_id}` | SHAP + rule provenance + attention | Analyst |
| `POST /narratives/{alert_id}` | TEE-LLM narrative/summary | Analyst |
| `POST /entities/{id}/unmask` | Re-identify tokenized PII (audited) | Senior+ |
| `GET/POST/PUT /rules` | Rule/threshold CRUD (change-controlled) | Compliance |
| `GET /models`, `POST /models/{id}/promote` | Registry view/promotion | Model Eng (+sign-off) |
| `GET /drift`, `GET /metrics/model` | Drift & model quality | Model Eng |
| `POST /feedback` | Active-learning label submission | Analyst |
| `GET /reports/fmr`, `GET /reports/crilc` | Regulatory export | Compliance |
| `GET /audit?actor=&entity=&from=&to=` | Immutable audit trail (incl. who-viewed-whom) | Auditor |
| `GET /admin/users`, `POST /admin/users` | User/role mgmt | Platform Admin |
| `GET /health`, `GET /metrics` | Liveness + Prometheus | service |

## 4. RBAC roles (blueprint Part 24.1)
Analyst · Senior Investigator · Team Lead/MLRO · Compliance Officer · Auditor · Model Engineer/Data Scientist · Platform Admin · Service accounts. **SoD rule:** whoever deploys models cannot label data or close their own alerts; whoever investigates cannot unilaterally tune the rules that generate their alerts. PII unmask is a separate, audited permission.

## 5. EDD disposition / feedback (request → response)
```http
POST /api/v1/alerts/alr_3d7e22/disposition
{ "outcome":"fraud", "notes":"Confirmed shell beneficiary; maker-checker collusion.", "evidence_ids":["evt_8f2a1c90"] }
```
```json
{ "alert_id":"alr_3d7e22","status":"confirmed_fraud","label_written":true,
  "feedback_queued_for_retraining":true,"audit_id":"aud_99f0c1" }
```

## 6. Model-serving interface (ML ↔ BACKEND)
- Models served via ONNX Runtime/Triton (port 8001). Input = assembled feature vector (Feast online keys); output = per-layer score (0–1) + optional reason-code payload. BACKEND fuses (L6) → calibrated 0–100 + severity×confidence. Every score persists `model_version` for reproducibility.

## 7. Narrative LLM (BACKEND ↔ ML gateway)
`POST /narratives/{alert_id}` → tokenized alert context → TEE LLM (NEAR AI primary / Groq secondary / **deterministic Jinja template fallback** — UI never breaks). Every narrative writes an audit memo: `provider`, `tee_attested`, `attestation_id`, `model`, `prompt_hash`, `ts`.

---
*BACKEND laptop: keep this current with the real implementation. Others: integrate against this, do not guess.*
