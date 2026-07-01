# Hawk-Eye — Real-Time Insider & Privileged-User Fraud Detection

> 👉 **New here / non-technical? Start with [`GETTING_STARTED.md`](GETTING_STARTED.md)** — a plain-English guide
> to what this is, how to run it in 2 minutes, how it works, and a glossary of every term.

A production-shaped, on-prem, **alert-only** insider-fraud detection platform for a public-sector bank, built local-first on **synthetic data**. Source of truth for *what* to build: [`Insider_Fraud_Detection_Implementation_Blueprint (2).md`](Insider_Fraud_Detection_Implementation_Blueprint%20(2).md) (34 parts). Source of truth for *how / in what order*: [`BUILD_PLAN.md`](BUILD_PLAN.md) (6 workstreams → 149 tasks).

**🔴 Live:** **https://hawk-eye.nineagents.in** — auto-deployed from `main` on every push (AWS Lightsail; `.github/workflows/deploy-lightsail.yml`).

## What it detects
Insider & privileged-user fraud: SWIFT/LoU abuse, new-beneficiary-then-high-value-approve, dormant-account drain, direct DB manipulation, entitlement self-grant, bulk data exfiltration, maker-checker collusion rings, fake-vendor / ghost-payroll, rogue trading, and AML alert-suppression. Every event is **scored 0–100 with reason codes and explained** for a human EDD decision — the system **never auto-blocks money**.

## The 8-layer detection stack (L0→L7)
A defence-in-depth funnel of complementary detectors — full technical write-up in [`docs/DETECTION_LAYERS.md`](docs/DETECTION_LAYERS.md):

| Layer | Technique | Catches |
|---|---|---|
| **L0** event | canonical actor/action/object/context/linkage schema (synthetic simulator) | — |
| **L1** rules / BRE | deterministic SoD + toxic-combo predicates, hard-short-circuit (<5 ms) | known typologies, cold-start |
| **L2** UEBA | IsolationForest + ECOD + AutoEncoder ensemble, peer-relative | novel / behavioural anomalies |
| **L3** GBDT | LightGBM (default) + TreeSHAP, calibrated | precision scoring on labelled typologies |
| **L4** sequence | USAD / TranAD / Anomaly-Transformer / LAXCAT (gated, async) | low-and-slow session drift |
| **L5** graph | XGB-on-graph / GraphSAGE (async) | collusion rings, shared-identity links |
| **L6** fusion | transparent stacked meta-learner + isotonic calibration | one calibrated 0–100 score + reason codes |
| **L6.5** interdiction | privileged-action gate → ALLOW / STEP_UP / HOLD (policy-authored, four-eyes) | second-approver review of held staff actions |
| **L7** dashboard | React investigator console (RBAC, alert-only) | human EDD triage |

Graceful degradation: if the model server is unavailable it falls back to **L1 rules only** — it never goes dark, and never auto-blocks.

## Run locally
Full guide in [`GETTING_STARTED.md`](GETTING_STARTED.md). Quick start:
- **Frontend (mock data, no backend needed):** `cd frontend && npm install && npm run dev` → http://localhost:5173 (`VITE_USE_MOCKS=true`).
- **Backend (FastAPI):** run the API on `:8000` (OpenAPI/Swagger at `/docs`); point the frontend at it with `VITE_USE_MOCKS=false`. The root `docker-compose` brings up the full stack (ClickHouse/Postgres/Redis/Kafka…).

## Tech stack
- **Frontend:** React 19 · Vite 8 · TypeScript 5.6 · Tailwind 3.4 · Radix UI · TanStack Query/Table/Virtual · Recharts · Cytoscape · React Router 7 · MSW · Vitest · Playwright.
- **Backend:** FastAPI · Pydantic 2 · JWT/Authlib RBAC · ClickHouse / Postgres / Redis (guarded, local fallbacks).
- **ML:** scikit-learn · PyOD · LightGBM / XGBoost / CatBoost · PyTorch · PyTorch-Geometric · SHAP · ONNX Runtime.
- **Platform:** Kafka/Flink (guarded) · MLflow · Prometheus/Grafana · Docker · Caddy on AWS Lightsail.
- Exact pins: [`frontend/package.json`](frontend/package.json), [`backend/pyproject.toml`](backend/pyproject.toml), `deploy/versions.bom.yaml`.

## Key API surfaces (`/api/v1`, JWT + RBAC)
Authoritative contract in [`BACKEND.md`](BACKEND.md) §3; index in [`docs/openapi-index.md`](docs/openapi-index.md); live spec at `/docs`.
- **Alerts / EDD:** `GET /alerts` · `/alerts/stats` · `/alerts/{id}` · `POST /alerts/{id}/{assign,disposition,block-request}`.
- **Explainability:** `GET /explanations/{id}` (fusion breakdown · per-layer model lineage · SHAP · rule provenance · L4 attention · structured L5 graph) · `POST /narratives/{id}` (TEE-attested).
- **Entity-360:** `GET /entities/{id}` + `/timeline` `/graph` `/peers` `/risk-index` `/score-history` `/layer-scores`.
- **Oversight / analytics:** `GET /activity/sub-threshold` · `/analytics/typologies` · `/graph` · `/audit` · `/services/status`.
- **Interdiction (L6.5):** `/api/v1/action-gate/*` → ALLOW / STEP_UP / HOLD (four-eyes, audited).
- **Rules / models / reports:** four-eyes rule changes · signed model promotion + kill-switch · CRILC / FMR / CFR draft exports.

## Golden rules (every laptop, every task)
1. **Alert-only.** The system scores and explains; a human decides. **It never auto-blocks money.**
2. **On-prem + synthetic.** No real bank systems, no cloud creds, no real PII. Everything runs locally on the synthetic simulator + public datasets. Real feeds/creds/hardware are **SCAFFOLD**; human/legal/hardware acts are **MOCK**.
3. **Validate against the blueprint.** No task is "done" until the matching blueprint Part's requirement is met. Cite the Part in your commits and your laptop log.
4. **Nothing is dropped.** The 6 workstreams partition the entire blueprint. If you find a blueprint requirement that isn't in your task list or anyone else's, raise it in `CONTEXT.md` immediately.

## The 6 workstreams (one laptop each)
| # | Workstream | Owns dir(s) | Prompt |
|---|---|---|---|
| 1 | 📥 **DATA** — data & ingestion | `data/` | [prompts/01_DATA.md](prompts/01_DATA.md) |
| 2 | 🤖 **ML** — models & MLOps | `ml/` | [prompts/02_ML.md](prompts/02_ML.md) |
| 3 | ⚙️ **BACKEND** — services & API | `backend/` + owns `BACKEND.md` | [prompts/03_BACKEND.md](prompts/03_BACKEND.md) |
| 4 | 🖥️ **FRONTEND** — dashboard | `frontend/` | [prompts/04_FRONTEND.md](prompts/04_FRONTEND.md) |
| 5 | 🗄️ **DATABASE** — storage | `db/` | [prompts/05_DATABASE.md](prompts/05_DATABASE.md) |
| 6 | 🏗️ **PLATFORM** — infra/security/governance/ops | `platform/`, `infra/`, `.github/`, root `docker-compose.yml` | [prompts/06_PLATFORM.md](prompts/06_PLATFORM.md) |

## The four kinds of coordination MD files
- **[`CONTEXT.md`](CONTEXT.md)** — shared full context. **Everyone appends** decisions, interfaces, and integration notes here.
- **[`BACKEND.md`](BACKEND.md)** — the backend/integration **contract** (event schema, alert schema, API routes, RBAC, score/reason-code shapes). **Owned by the BACKEND laptop**; everyone else **reads** it to integrate.
- **[`TODO.md`](TODO.md)** — shared task board. Each laptop keeps its rows current.
- **`docs/laptops/<NN-workstream>.md`** — each laptop's **own** working log (decisions, files created, deviations, blockers).

## Repo layout
```
data/        ML-ready synthetic data, simulator, L0 schema, connectors, features (DATA laptop)
ml/          models L2–L6, training, eval, mlops, explainability, LLM gateway (ML laptop)
backend/     FastAPI, L1 rules, fusion service, serving, EDD loop, tokenization, reports (BACKEND laptop)
frontend/    React/TS investigator dashboard (FRONTEND laptop)
db/          ClickHouse/Postgres/Redis/object-store/WORM/registry schemas & config (DATABASE laptop)
infra/       docker-compose, k8s, terraform (PLATFORM laptop)
platform/    security, governance mocks, observability, DR, ops (PLATFORM laptop)
tests/       cross-workstream integration tests (PLATFORM laptop owns harness; all contribute)
docs/        coordination docs + per-laptop logs
prompts/     the 6 build prompts (one per laptop)
```

## Merge model
Each laptop works on branch `hawk-eye/<workstream>` and only edits files **under its owned dirs** + its own laptop log + appends to shared MD files. Merges to `main` integrate cleanly because ownership is disjoint. Cross-workstream interfaces are agreed in `BACKEND.md` / `CONTEXT.md` **before** coding against them.
