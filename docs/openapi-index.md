# OpenAPI Index — API surface map

> **Owner:** PLATFORM (Laptop 06) maintains *this index* · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 24.2** (API routing, OpenAPI-style), **Part 34.3**
> (API docs as a required knowledge asset).
>
> This is an **INDEX** linking the API surfaces in Hawk-Eye:
> 1. the **BACKEND application API** (owned by BACKEND, contract in `BACKEND.md` §3),
> 2. the **PLATFORM governance-api** routes (read-only governance view),
> 3. the **PLATFORM hitl-gate** routes (the natural-justice classification gate), and
> 4. the **L6.5 action-gate** routes (the privileged-action interdiction PDP, `:8096`).
> Each service publishes its own live OpenAPI/Swagger at `/docs` (FastAPI) — this file is the map,
> not the spec.

---

## 1. BACKEND application API (BACKEND owns — `BACKEND.md` §3)

Base `/api/v1`, JWT required, RBAC = minimum role. Live OpenAPI at `http://localhost:8000/docs`.
Full route table is in **[`BACKEND.md` §3](../BACKEND.md)** — highlights:

| Method & path | Purpose | RBAC |
|---|---|---|
| `POST /auth/login`, `POST /auth/refresh` | OIDC token exchange/refresh | public |
| `GET /alerts?status=&risk_gte=&assignee=` | Ranked alert queue | Analyst |
| `GET /alerts/{id}` | Full alert (score, reason codes, layers) | Analyst |
| `POST /alerts/{id}/disposition` | EDD outcome → **label** | Analyst |
| `POST /alerts/{id}/block-request` | Raise block request (**human action, never auto**) | Analyst→Lead |
| `GET /entities/{id}` · `/timeline` · `/graph` · `/peers` | Entity-360 | Analyst |
| `GET /explanations/{alert_id}` | SHAP + rule provenance + attention | Analyst |
| `POST /narratives/{alert_id}` | TEE-LLM narrative/summary (explanation only) | Analyst |
| `POST /entities/{id}/unmask` | Re-identify tokenized PII (**audited**) | Senior+ |
| `GET/POST/PUT /rules` | Rule/threshold CRUD (change-controlled) | Compliance |
| `GET /models`, `POST /models/{id}/promote` | Registry view/promotion (+ sign-off) | Model Eng |
| `GET /reports/fmr`, `GET /reports/crilc` | Regulatory export | Compliance |
| `GET /audit?...` | Immutable audit trail (incl. who-viewed-whom) | Auditor |
| `GET /health`, `GET /metrics` | Liveness + Prometheus | service |

> The **alert-only** invariant lives here: `block-request` is a *human-raised* request — there is
> no auto-block route anywhere in the API (Part 16; *SBI v. Rajesh Agarwal*).

### 1a. Recently added (surfacing overhaul · 10× insider depth · L6.5)

Beyond the highlights above, the live `/api/v1` surface now also includes (all under `/api/v1`,
JWT + RBAC; see the live `/docs` for exact shapes):

| Method & path | Purpose | RBAC |
|---|---|---|
| `GET /alerts/stats` | Portfolio counts for the dashboard header (open / high / SLA-at-risk / confirmed) | Analyst |
| `GET /activity/sub-threshold` | The "hidden 95%" — detection funnel + near-miss watchlist (scored <70, not alerted) | Analyst |
| `GET /analytics/typologies` | Fraud-typology prevalence + confirmed-rate + exposure | Analyst |
| `GET /entities/{id}/risk-index` | Continuous per-user insider-risk index (M2.1) | Analyst |
| `GET /entities/{id}/score-history` · `/layer-scores` | Risk-over-time + per-layer (L2–L6) score timeline | Analyst |
| `GET /explanations/{id}/report` | Downloadable, audit-grade explainability report (SAR/FMR pack) | Analyst |
| `GET /narratives/{id}/attestation` | Real NEAR AI Cloud Intel-TDX TEE attestation | Analyst |
| `GET /graph?min_score=&limit=` | Global cross-entity risk link-graph | Analyst |
| `GET /cases` · `/cases/{id}` · `POST /cases/{id}/{status,assign,notes}` | Case management | Analyst |
| `POST /rules` · `PUT /rules/{code}` · `POST /rules/{change_id}/approve` | Four-eyes rule-change proposal + approval | Compliance |
| `POST /models/{id}/{disable,enable}` · `GET /models/{id}/state` | Model kill-switch (FREE-AI: halt without redeploy) | Model Eng |
| `GET /drift` · `GET /metrics/model` | Drift metrics · model-quality metrics | Model Eng |
| `POST /feedback` | Active-learning label submission (EDD feedback loop) | Analyst |
| `GET /reports/cfr` · `/reports/ews-coverage` · `/reports/kris` | CFR feed · EWS coverage map · board/SCBMF KRIs | Compliance |
| `GET /rfa/{id}` · `POST /rfa/{id}/{examination,show-cause,close}` | RFA staff-accountability lifecycle (RBI FRM 2024) | Compliance |
| `POST /compliance/{transfers,data-principal}` | DPDP cross-border transfer log · data-principal rights intake | Compliance |
| `GET /services/status` | Service map + live status | Auditor |
| `POST /events/ingest` | Ingest one L0 event (full run or L1 short-circuit) | service |

---

## 2. PLATFORM governance-api (PLATFORM owns — `:8093`)

Read-only governance view for the dashboard; backed by the governance DB (seeded approvals).
Live OpenAPI at `http://localhost:8093/docs`. Routes (`services/governance-api/`):

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /api/v1/governance/committees/{committee_id}/minutes` | Committee minutes (AI/Model-Risk, ISC, ITSC, Ethics, Board) |
| `GET /api/v1/governance/approval-queue` | Pending/decided approvals & sign-offs |
| `GET /api/v1/governance/board-pack` | Consolidated board pack (policies, validations, CAB) |
| `POST /api/v1/governance/incidents` | File a governance/cyber incident record |
| `GET /api/v1/governance/{artifact_type}` | Governance artifacts by type (policies, DPIA, validations…) |
| `GET /api/v1/go-live` | DB-backed go/no-go readiness gate (Part 34.6) |
| `GET /metrics` | Prometheus |

> Surfaces the seeded approvals — AI Policy **BR-2026-014**, BCP **BRC-2026-008**, DPIA
> **DPO-2026-004**, CAB **CAB-2026-033**, and the model-validation record for **`fusion-2026.2.0`**
> (see [`model-card-index.md`](./model-card-index.md)). These are the routes proposed to BACKEND in
> CONTEXT.md §8; PLATFORM serves them independently via governance-api.

---

## 3. PLATFORM hitl-gate (PLATFORM owns — `:8094`)

The **human-in-the-loop natural-justice gate** — the system flags; a human, with the accused's
hearing, classifies. Nothing is auto-classified as fraud. Live OpenAPI at
`http://localhost:8094/docs`. Routes (`services/hitl-gate/`):

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness |
| `POST /api/v1/classifications` | Open a `pending_review` classification for an alert |
| `GET /api/v1/classifications` | List classifications |
| `GET /api/v1/classifications/{cid}` | One classification (status, evidence, hearing record) |
| `POST /api/v1/classifications/{cid}/decision` | The **human decision** (approve/reject) — natural-justice gate |
| `GET /metrics` | Prometheus |

> This is the technical embodiment of the natural-justice requirement (Part 16; *SBI v. Rajesh
> Agarwal*, 2023): a classification only becomes final on a **recorded human decision** after the
> subject has been heard.

---

## 4. L6.5 action-gate — privileged-action interdiction PDP (`:8096`, `services/action-gate/`)

The **policy decision point** for held staff actions. It **decides** ALLOW / STEP_UP / HOLD on a
*reversible privileged action* (entitlement self-grant, maker+checker by the same actor, bulk export
from a privileged session, SWIFT/SO send, direct DB write); it **never auto-executes and never
blocks money** — approving a HOLD only *permits* human-initiated execution (four-eyes, no
self-review). Surfaced in the L7 console at `/interdiction`. Routes (also mounted under `/api/v1`):

| Method & path | Purpose | RBAC |
|---|---|---|
| `POST /action-gate/evaluate` | Evaluate a privileged action → `{ALLOW · STEP_UP · HOLD_FOR_REVIEW}` | service / policy |
| `GET /action-gate/holds` | The HOLD_FOR_REVIEW queue awaiting a second approver | DGM Compliance / AGM Vigilance |
| `POST /action-gate/holds/{id}/decide` | Four-eyes approve(permit)/reject with mandatory justification (audited) | DGM Compliance / AGM Vigilance |
| `GET /action-gate/policies` | Read-only interdiction policy list (hard HOLD vs soft STEP-UP) | DGM Compliance / AGM Vigilance |

> Consistent with **alert-only + natural justice**: this is a control on a *reversible staff action*
> with a human in the loop, not an auto-block of money and not an auto-classification of a person.

---

## How to regenerate / view the live specs

- Each FastAPI service serves its OpenAPI JSON at `/openapi.json` and Swagger UI at `/docs`.
- Contract-test the governance-api routes against the BACKEND route table with
  **`make contract-test`**.
- Inter-service URLs use compose service names (`http://backend:8000`, `http://governance-api:8093`,
  `http://hitl-gate:8094`) — see CONTEXT.md §7.

---

*This is an index. The BACKEND application API is owned by **BACKEND** (`BACKEND.md` §3); the
governance-api and hitl-gate routes are owned by **PLATFORM** (`services/`). Each service is the
source of truth for its own live OpenAPI document.*
