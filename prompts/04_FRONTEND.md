# Hawk-Eye — Laptop 04: FRONTEND — Claude Code Build Prompt

> You are the FRONTEND laptop in a 6-laptop build of the **Hawk-Eye** real-time insider & privileged-user fraud-detection platform. You build the **React + TypeScript investigator console** and merge into a shared git repo with 5 other laptops (DATA, ML, BACKEND, DATABASE, PLATFORM). This prompt is self-contained and exhaustive. Follow it exactly. When in doubt, **read the blueprint Part and validate against it** — never guess.

---

## 0. Mission & golden rules

**Mission.** Deliver the full investigator dashboard described in blueprint **Part 11** and **Part 24.4** — a thin React/TS client over the BACKEND REST API (which sits atop ClickHouse) that lets the fraud-investigation team **triage, investigate, explain, and act** on insider-fraud alerts, plus the role-specialized compliance/auditor/model-engineer/admin/reporting consoles. Every view is RBAC-gated. Sub-second drill-down. Explanations defensible for SAR/FMR filing.

**Golden rules (restate, obey on every task):**
1. **ALERT-ONLY.** The UI never auto-blocks money or auto-classifies. A human always decides. "Request block" is a *request* that routes to a Lead for approval; disposition requires an explicit human action. There is no UI path that takes an enforcement action without a human in the loop.
2. **ON-PREM + SYNTHETIC ONLY.** No real PII, no real bank feeds, no real credentials, no third-party SaaS calls from the browser. All data comes from the BACKEND API serving synthetic/simulator data. Tokenized PII by default; unmask is an audited backend call.
3. **VALIDATE-AGAINST-BLUEPRINT.** No task is "done" until the cited blueprint Part's requirement is met. Cite the Part in commits and your laptop log.
4. **NOTHING-DROPPED.** Every item in your task inventory and the must-cover checklist (§6) must be built. If you find a blueprint UI requirement not in your list or anyone else's, raise it in `CONTEXT.md` immediately.
5. **STAY-IN-LANE.** You edit **only** `frontend/`, your own laptop log `docs/laptops/04-frontend.md`, and you **append** (never overwrite) to shared `CONTEXT.md` and `TODO.md`. You **never** edit `BACKEND.md` (read-only for you), nor any other laptop's directory.

**Design philosophy (Part 11):** built around the investigator's actual workflow — triage → entity-360 → explanation → graph → peers → EDD action → reporting. ClickHouse-backed ad-hoc, high-cardinality queries over long history (you query it via BACKEND, never directly). Grafana is embedded (iframe) for ops/health, not reimplemented.

---

## 1. Mandatory reading before any code

Read these **in full** before writing any code, and re-read the three shared MD files at the **start of every session**:

**Blueprint Parts you OWN (read in full):** open `Insider_Fraud_Detection_Implementation_Blueprint (2).md` and read:
- **Part 11 — The investigator dashboard (the frontend)** (~lines 382–397): Core views (triage queue, entity-360, explanation panel, graph/link view, peer comparison, action & EDD, reporting) + Stack declaration (React+TS over ClickHouse, API in Rust/Go/Python, Grafana for ops).
- **Part 24.4 — UI / screens — what each persona sees** (~lines 945–960): every one of the 8 screens, field by field.
- **Part 24.1 — RBAC roles and permission matrix** (~lines 874–888): the 8 roles × 9 capabilities table + the SoD rule (Part 19.6). This drives every route guard and every conditionally-rendered control.
- **Part 24.5 — Sample payloads** (~lines 961–1026): the sample event, the sample alert (the exact shape your triage queue and alert detail render), the disposition request/response, and the worked burst → alert table. **Render against these exact shapes.**
- **Part 24.2 — API routing** (~lines 890–916): the REST route table — every screen is a client of these routes; the RBAC column tells you the minimum role.

**Blueprint Parts you REFERENCE (skim, do not own):**
- **Part 25 — TEE-attested narrative LLM gateway** (~lines 1029–1075): you render the narrative returned by `POST /narratives/{alert_id}` and the audit/provenance fields (`provider`, `tee_attested`, `attestation_id`); you must clearly **label** AI-generated text and show the `tee_attested` badge. You do not build the gateway (ML owns it; BACKEND exposes the route).
- **Part 18 / Part 10** (fusion + MLOps feedback loop): context for what reason codes and dispositions mean; the EDD disposition you POST becomes a label in the relabeling loop.
- **Part 23.2** (registry layout) and the drift section of Part 10: context for the model-engineer view.

**Plan & coordination files (read fully, every session):**
- `BUILD_PLAN.md` — the FRONTEND workstream section (13 tasks, 4 milestones) plus the cross-workstream dependency list at the bottom of the FRONTEND section.
- `CONTEXT.md` — shared brain; read the integration log (newest first); ports/service map (frontend = Vite on **5173**; backend API on **8000**; Keycloak on **8080**; Grafana on **3000**). Conventions: IDs (`evt_*`, `alr_*`, `EMP-*`, `RNG-*`, `aud_*`), time in **UTC ISO-8601** stored, displayed in **IST** on the frontend, money in INR.
- `BACKEND.md` — **the contract you integrate against** (owned by BACKEND, read-only for you): the L0 event JSON, the L6 alert JSON, the full API route table, RBAC roles, the EDD disposition request/response, the model-serving and narrative-gateway notes. **All your API calls bind to this.** If you need a contract change, propose it in `CONTEXT.md` and tag BACKEND — do not invent fields.
- `TODO.md` — your section (workstream 4); keep its rows current.
- `README.md` — repo layout and merge model.

---

## 2. The MD-file coordination protocol (the 4 files — exact read/write rules)

There are **four kinds** of MD files. Obey these rules precisely.

| File | Who owns | Your rule |
|---|---|---|
| **`CONTEXT.md`** | Shared (everyone appends) | **Read first, every session.** When you make a cross-cutting decision/interface affecting others (a new query param you need, a contract gap, a port, a convention, a deviation), **append** an entry to the INTEGRATION LOG at the bottom, **newest first**, format `### YYYY-MM-DD — [FRONTEND] — title`. **Never delete or overwrite** others' entries. |
| **`BACKEND.md`** | **BACKEND laptop owns it** | **READ-ONLY for you.** This is the canonical contract (event schema, alert schema, API routes, RBAC, disposition shapes). You integrate against it. If you need a change (e.g., a missing field, a new filter), **do not edit it** — propose the change in `CONTEXT.md` and tag BACKEND. |
| **`TODO.md`** | Shared board (each laptop owns its rows) | Keep the **FRONTEND** section (§4) current: `[ ]` todo, `[~]` in-progress, `[x]` done (only when blueprint-validated), `[!]` blocked. Put cross-laptop blockers in §7 and mirror them in `CONTEXT.md`. |
| **`docs/laptops/04-frontend.md`** | **You own it** | Your working log. Record: decisions, files created, **blueprint validations** (task → Part → how verified), deviations (and why), blockers, stubs you created for not-yet-built backend endpoints, and integration notes. Update it as you go; never let it go stale. |

**Session start ritual (every session):** (1) read `CONTEXT.md` (esp. new integration-log entries), (2) read `BACKEND.md` (the contract may have changed — regenerate your API types if so), (3) read `TODO.md` FRONTEND rows, (4) read your `docs/laptops/04-frontend.md` to recover state. Then code.

**Session end ritual:** update `TODO.md` rows, append any cross-cutting decisions to `CONTEXT.md`, and write a dated entry in your laptop log (what you did, what you validated against the blueprint, what's stubbed, what's blocked).

---

## 3. Ownership, directories & git/merge discipline

**You own:** `frontend/` only. Plus your laptop log `docs/laptops/04-frontend.md`. Plus append-rights to `CONTEXT.md` and `TODO.md`.

**You must NOT edit:** `BACKEND.md`, `backend/`, `ml/`, `data/`, `db/`, `infra/`, `platform/`, `.github/`, root `docker-compose.yml`, or any other laptop's log. If you need something there, stub it (below) and raise it in `CONTEXT.md`.

**Branch:** `hawk-eye/frontend`. Always work on this branch; never commit directly to `main`.

**Commit format:** `[FRONTEND] <TASK-ID> <message> (blueprint Part X)`
- Example: `[FRONTEND] FRONTEND-4 triage queue ranked by risk×exposure×confidence with SLA timer (blueprint Part 11, 24.4)`
- One logical change per commit; cite the Part(s) the task validates against.

**How to stub a not-yet-built dependency (BACKEND endpoint not ready, ML reason-code shape not finalized, etc.):**
1. Build against the **contract in `BACKEND.md`** (the alert/event/disposition JSON shapes and route table are already defined there).
2. Add a **mock service layer**: `frontend/src/lib/mocks/` with MSW (Mock Service Worker) handlers returning the exact `BACKEND.md` sample payloads (the Part 24.5 alert, event, disposition, etc.). Gate it behind an env flag `VITE_USE_MOCKS=true` so the same components run against the real API when it lands.
3. Keep the typed API client (`src/lib/apiClient.ts`) as the single seam — components call the client, not fetch directly, so flipping mock↔real is one switch.
4. Log the stub in your laptop log and, if it implies a contract need, append to `CONTEXT.md` tagging BACKEND.
5. **Never** hardcode mock data inside components; never commit `VITE_USE_MOCKS=true` as the default for integration builds.

**Merge cleanliness:** because ownership is disjoint, merges to `main` integrate cleanly. Only touch shared MD files by **appending**. Resolve conflicts in shared MD by keeping both entries.

---

## 4. Tech stack & pinned versions (this workstream)

Pin exact patch versions in `frontend/package.json` + lockfile. Base BOM from blueprint **Part 24.3** (verify latest patch before locking; track CVEs):

| Component | Version (pin) | Role |
|---|---|---|
| **React** | 19.x | UI framework (blueprint Part 24.3, Part 11) |
| **TypeScript** | 5.6.x | types (blueprint Part 24.3) |
| **Node** | 22.x | toolchain (blueprint Part 24.3) |
| **Vite** | latest 5.x compatible with React 19 | dev server / build (port 5173 per CONTEXT.md) |
| **TanStack Query** (react-query) | latest stable | server-state, caching, polling for SLA timers |
| **TanStack Table** + **TanStack Virtual** | latest stable | virtualized triage queue / audit table over large result sets |
| **React Router** | latest v6/v7 stable | RBAC-aware routing |
| **oidc-client-ts** (or Keycloak JS adapter) | latest stable | OIDC SSO / PKCE / token refresh (Keycloak 25.x issuer) |
| **Cytoscape.js** | latest stable | graph/link view (beneficiary networks, collusion subgraphs) |
| **Recharts** or **visx** | latest stable | SHAP bar charts, peer-comparison box/distribution plots, KRI/trend charts |
| **Tailwind CSS** + **shadcn/ui** | latest stable | design system / components |
| **MSW** (Mock Service Worker) | latest stable | mocking not-yet-built BACKEND endpoints |
| **Playwright** | latest stable | e2e tests |
| **Vitest** + **@testing-library/react** | latest stable | unit/component tests |
| **ESLint** + **Prettier** + **typescript-eslint** | latest stable | lint/format/type gate |

**Other pins referenced (not yours to build, but you integrate against):** Keycloak 25.x (OIDC), Grafana 11.x (iframe embed), FastAPI 0.115 backend on 8000, ClickHouse 25.x behind the API. Record your exact pinned versions in your laptop log on first install.

---

## 5. Interface contracts / the seams (what you consume & produce; reference BACKEND.md)

You are a **thin client**. You **produce** no contracts of your own (CONTEXT.md §4 lists FRONTEND's published contracts as "—"); you **consume** BACKEND's. Bind every call to `BACKEND.md`.

### What you consume (from `BACKEND.md` §3 — the API; base `/api/v1`, JWT required, RBAC = min role):
| Route | You use it in |
|---|---|
| `POST /auth/login`, `POST /auth/refresh` | Login/SSO screen, token refresh (FRONTEND-2) |
| `GET /alerts?status=&risk_gte=&assignee=` | Triage queue (FRONTEND-4) |
| `GET /alerts/{id}` | Alert/case detail header (FRONTEND-6) |
| `POST /alerts/{id}/assign` | Claim/assign (FRONTEND-4, FRONTEND-5) |
| `POST /alerts/{id}/disposition` | EDD action panel → label (FRONTEND-11) |
| `POST /alerts/{id}/block-request` | EDD request-block (FRONTEND-11) |
| `GET /entities/{id}` | Entity-360 profile (FRONTEND-7) |
| `GET /entities/{id}/timeline` | Entity-360 unified timeline (FRONTEND-7) |
| `GET /entities/{id}/graph` | Graph/link view (FRONTEND-9) |
| `GET /entities/{id}/peers` | Peer comparison (FRONTEND-10) |
| `GET /explanations/{alert_id}` | Explanation panel: SHAP + rule provenance + attention (FRONTEND-8) |
| `POST /narratives/{alert_id}` | AI narrative in explanation panel (FRONTEND-8) |
| `POST /entities/{id}/unmask` | Audited PII unmask control (FRONTEND-3, used across detail views) |
| `GET/POST/PUT /rules` | Compliance rules/threshold change-control (FRONTEND-12) |
| `GET /models`, `POST /models/{id}/promote` | Model-engineer registry view (FRONTEND-13) |
| `GET /drift`, `GET /metrics/model` | Model-engineer drift dashboards (FRONTEND-13) |
| `POST /feedback` | Active-learning label submission from EDD panel (FRONTEND-11) |
| `GET /reports/fmr`, `GET /reports/crilc` | CRILC/FMR export (FRONTEND-12) |
| `GET /audit?actor=&entity=&from=&to=` | Auditor view (FRONTEND-13) |
| `GET /admin/users`, `POST /admin/users` | Admin view (FRONTEND-13) |
| `GET /health`, `GET /metrics` | Admin/system-health (FRONTEND-13) |

### Canonical payload shapes you render (from `BACKEND.md` §1/§2 and Part 24.5):
- **L6 alert** (triage row + detail header): `alert_id`, `entity_id`, `risk_score` (0–100), `severity`, `confidence` (0–1), `status`, `created_ts`, `contributing_layers[]`, `reason_codes[]` (each `{source: rule|shap|graph, ...}`), `exposure_inr`, `sla_due_ts`, `pii_tokenized`.
- **Reason codes**: `rule` → `{code, detail}`; `shap` → `{feature, contribution}`; `graph` → `{detail}` (e.g. ring_id). Sequence **attention** (LAXCAT) and **graph evidence** (GNNExplainer) arrive via `GET /explanations/{alert_id}`.
- **L0 event** (timeline rows): `actor` (employee_id/role/dept/branch/tenure/peer_group/privileged_flag/leaver_flag), `action` (verb/channel/maker_checker), `object` (beneficiary/account/amount/currency), `context` (src_ip/device/geo/session/layer/is_off_hours).
- **Disposition** request `{outcome: fraud|false_positive|inconclusive, notes, evidence_ids[]}` → response `{alert_id, status, label_written, feedback_queued_for_retraining, audit_id}`.
- **Narrative** memo fields to display: `provider` (near_ai/groq/template), `tee_attested` (bool — show a badge), `attestation_id`, `model`, `prompt_hash`, `ts`.

### The seams — name the owner, state your integration responsibility:
- **L0 event schema** — **DATA owns**; you render its field groups (actor/action/object/context) on the entity-360 timeline. Integration: read the shapes via BACKEND.md (BACKEND consumes them and serves you via `/entities/{id}/timeline`); never reach into `data/`.
- **L1 rules / SoD / toxic-combination matrix** — **BACKEND owns the engine**. You render rule-provenance reason codes in the explanation panel and provide the **change-controlled rule/threshold editor UI** (FRONTEND-12) that calls `GET/POST/PUT /rules`; BACKEND enforces four-eyes approval server-side. You only build the UI; you never enforce rules client-side.
- **Models L2–L6 / fusion / reason-code assembly** — **ML trains/produces** SHAP, LAXCAT attention, GNNExplainer evidence; **BACKEND runs the online fusion + reason-code assembly** (Part 18) and serves them. You render. Integration: bind to `/explanations/{id}` and the alert `reason_codes[]`.
- **LLM narrative gateway** — **ML owns the gateway/prompt/fallback**; **BACKEND exposes `POST /narratives/{alert_id}`**; **PLATFORM owns egress allow-list + TEE-attestation MOCK**. Your responsibility: render the narrative, **clearly label it as AI-generated**, and surface the `tee_attested` badge + provider; never break the UI if the narrative call fails (BACKEND's deterministic Jinja fallback guarantees a body — handle the degraded/`tee_attested=false` case gracefully).
- **PII tokenization / re-identification vault** — **BACKEND owns** the tokenization service + vault and the `POST /entities/{id}/unmask` request path; **PLATFORM owns the HMAC key + egress controls**. Your responsibility: show tokenized PII by default (`pii_tokenized: true`), provide a **masked-PII component with an audited unmask control** that calls `/entities/{id}/unmask`, and render unmask only for roles permitted by the RBAC matrix (Senior+). The unmask is audited server-side; you must show that it is logged.
- **Reporting (FMR / CRILC / EWS / RFA)** — **BACKEND owns the generators**; **you (FRONTEND) own the export UI**; **DATABASE stores outputs**. Your responsibility: the EWS/RFA coverage dashboard + one-click CRILC/FMR export buttons that call `/reports/*`.
- **Audit / WORM** — **DATABASE owns the immutable/WORM store**; **BACKEND writes audit events**; **everyone's actions (incl. investigators) are audited.** Your responsibility: the read-only auditor view over `GET /audit` (incl. who-viewed-whom), and showing the `audit_id` confirmation on every action you submit. Note: your own viewing/unmasking actions are audited server-side ("watch-the-watchers") — surface this honestly in the UI.
- **Source connectors / integration runtime** — DATA + PLATFORM own; not your concern (you never touch raw feeds).
- **Governance / fairness** — ML produces model cards/fairness metrics; PLATFORM produces governance MOCKs. Your model-engineer view renders the metrics/drift; you do not build governance docs.
- **Testing** — you own your **unit/component/contract/e2e** tests; **PLATFORM owns the cross-workstream integration-test harness + CI**. Contribute your tests; don't build the cross-WS harness.

---

## 6. Your complete task list (every task, grouped by milestone)

Status legend: **REAL** = works on synthetic/mock data locally. All 13 FRONTEND tasks are **REAL** (no SCAFFOLD/MOCK). Each task lists: **ID · what · deliverable path · status · blueprint ref · acceptance check.** A task is "done" only when the acceptance check passes AND the blueprint ref is validated AND `TODO.md`/laptop-log updated.

> **Inventory mapping note (nothing dropped):** the 22 granular inventory items map onto these 13 tasks as annotated. The must-cover capability checklist is covered across FRONTEND-1…13 as marked. Cross-check both before declaring any milestone done (see §9 gate).

### M1 — Foundations: app shell, SSO, RBAC

**FRONTEND-1 — React+TS app scaffold, design system, typed API client**
- What: Vite + React 19 + TS 5.6 project; `src/app` shell (layout, nav, error boundary, toast); `src/lib/apiClient.ts` typed wrapper over the BACKEND REST surface with generated types from the BACKEND.md contract; TanStack Query provider; shadcn/Tailwind design system; routing skeleton; MSW mock layer (`src/lib/mocks/`) gated by `VITE_USE_MOCKS`. IST display helpers (store UTC, render IST). ID-format helpers for `evt_*`/`alr_*`/`EMP-*`/`RNG-*`/`aud_*`.
- Deliverable: `frontend/` (Vite project), `frontend/src/app/*`, `frontend/src/lib/apiClient.ts`, `frontend/src/lib/mocks/*`, `frontend/src/lib/format.ts`.
- Status: REAL. Blueprint ref: **Part 11 (Stack), Part 24.3 (versions), Part 24.5 (payload shapes to type against)**.
- Acceptance: app boots on :5173; `apiClient` exposes a typed method per BACKEND.md route; MSW serves the Part 24.5 sample alert/event/disposition; `npm run build` + `tsc --noEmit` clean. (Inventory items: stack declaration #5,#13; must-cover: React+TS app, typed API client to BACKEND APIs.)

**FRONTEND-2 — Login / SSO screen (OIDC redirect, MFA, session controls)**
- What: `src/auth/` with oidc-client-ts integration against Keycloak (issuer on :8080); `LoginPage`; PKCE redirect + callback handling; silent + manual token refresh via `POST /auth/refresh`; session-timeout controls (idle logout, refresh-before-expiry, explicit logout); MFA handled by the IdP redirect flow (UI surfaces the MFA step, does not implement factors). Short-lived JWT stored in memory (not localStorage) per security posture.
- Deliverable: `frontend/src/auth/oidc.ts`, `frontend/src/auth/LoginPage.tsx`, `frontend/src/auth/session.ts`.
- Status: REAL. Blueprint ref: **Part 24.4 screen 1 (l.946), Part 24.1 (OIDC/OAuth2 + JWT)**.
- Acceptance: unauthenticated user is redirected to IdP; callback exchanges code → token; expiring token auto-refreshes; idle timeout logs out; logout clears tokens. (Inventory item: UI screen 1 #14; must-cover: login/SSO (OIDC) + MFA + session controls.)

**FRONTEND-3 — RBAC-aware routing, role-view shells, audited PII-unmask control**
- What: `src/auth/rbac.tsx` encoding the **Part 24.1 capability matrix** (8 roles × 9 capabilities) as client-side route/component guards (defense-in-depth; server enforces authoritatively); role-scoped route shells for Analyst / Senior Investigator / Team Lead-MLRO / Compliance Officer / Auditor / Model Engineer / Platform Admin; a reusable **`<MaskedPII>`** component that renders tokens by default and exposes an **audited unmask** action calling `POST /entities/{id}/unmask`, shown only for roles with the unmask capability (Senior+, case-scoped/logged for Analyst per the matrix). Enforce the **SoD rule (Part 19.6)** in the UI: hide "tune rules" from the investigator who generated the alert; hide "label/close own alert" controls from a Model Engineer.
- Deliverable: `frontend/src/auth/rbac.tsx`, `frontend/src/auth/capabilities.ts`, `frontend/src/components/MaskedPII.tsx`, `frontend/src/auth/RoleShell.tsx`.
- Status: REAL. Blueprint ref: **Part 24.1 (l.874–888), Part 19.6 SoD, Part 25.3 (tokenized PII / unmask permission)**.
- Acceptance: each route renders only for permitted roles (all 9 capabilities encoded exactly per matrix incl. the ⚠️ conditional cells: Analyst unmask = case-scoped+logged, Lead unmask = logged, Model Eng = de-identified only, Compliance tune-rules = change-controlled); `<MaskedPII>` shows token until unmask; unmask call carries auth + is shown as logged; SoD-forbidden controls are absent for the relevant role. (Inventory items: RBAC-aware views; must-cover: RBAC-gate every view, audited unmask.)

### M2 — Triage and case workflow

**FRONTEND-4 — Triage queue (Analyst home): ranked, deduplicated, SLA timer, claim**
- What: `src/views/TriageQueue.tsx` — virtualized TanStack table over `GET /alerts?status=&risk_gte=&assignee=`. Order rows by **fused risk × monetary exposure × confidence** (compute the composite ordering from `risk_score`, `exposure_inr`, `confidence`; respect any server ordering, fall back to client sort). **Dedup per entity** (group multiple alerts for the same `entity_id`; show count, surface the highest-risk representative). Filters: status, risk (`risk_gte`), assignee, type. Per-row **SLA/TAT countdown timer** from `sla_due_ts` (RBI ≤30-day; visually warn as it approaches/breaches; live-tick via TanStack Query refetch/interval). One-click **claim/assign** via `POST /alerts/{id}/assign`. Severity/confidence badges, contributing-layer chips, tokenized entity id.
- Deliverable: `frontend/src/views/TriageQueue.tsx`, `frontend/src/components/SlaTimer.tsx`, `frontend/src/components/AlertRow.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.387), Part 24.4 screen 2 (l.947), Part 24.5(b) alert shape**.
- Acceptance: queue ranks by risk×exposure×confidence; dedups per entity; all four filters work; SLA timer counts down and warns/breaches correctly; claim updates assignee; virtualized to thousands of rows without jank. (Inventory items: triage queue #6, UI screen 2 #15; must-cover: triage queue ranked + deduped + SLA/TAT timer.)

**FRONTEND-5 — Case management: assignment, status, linked alerts, notes, history**
- What: `src/views/CaseManagement.tsx` + `src/views/CaseDetailShell.tsx` — case list; assignment + status workflow (open → in-progress → escalated → closed states reflecting backend status enum); linked-alert panel (alerts grouped into a case); threaded notes; activity/history feed (who did what, when — sourced from case store / audit). Status transitions are human actions only (alert-only rule).
- Deliverable: `frontend/src/views/CaseManagement.tsx`, `frontend/src/views/CaseDetailShell.tsx`, `frontend/src/components/CaseNotes.tsx`, `frontend/src/components/CaseHistory.tsx`.
- Status: REAL. Blueprint ref: **Part 24.4 screen 4 (l.955)**.
- Acceptance: cases list/assign/transition status; linked alerts render; notes thread persists via API; history shows activity. (Inventory item: UI screen 4 #17; must-cover: case management.)

### M3 — Investigation surface: the alert/case detail (the workhorse screen)

**FRONTEND-6 — Alert/Case detail layout + header (score, severity, SLA)**
- What: `src/views/AlertDetail.tsx` — composition shell binding `GET /alerts/{id}`; **header** shows risk score (0–100), severity×confidence, status, SLA timer; hosts tabbed/stacked sub-panels (Entity-360 timeline, Explanation, Graph, Peer comparison, EDD action). Tokenized `entity_id` with `<MaskedPII>`. Contributing-layers chips.
- Deliverable: `frontend/src/views/AlertDetail.tsx`, `frontend/src/components/AlertHeader.tsx`.
- Status: REAL. Blueprint ref: **Part 24.4 screen 3 header (l.948–949), Part 24.5(b)**.
- Acceptance: header renders all fields from the sample alert; sub-panels mount; SLA timer consistent with queue. (Inventory item: UI screen 3 header #16.)

**FRONTEND-7 — Entity-360 unified timeline**
- What: `src/components/Entity360Timeline.tsx` — **one timeline** merging the actor's **transactions, access events, DB/data-layer activity, and HR/change context** over `GET /entities/{id}` + `GET /entities/{id}/timeline`. Render the L0 event field groups (actor/action/object/context); color/icon by `context.layer` (application / data / identity / change) and `action.verb`; flag `is_off_hours`, `privileged_flag`, `leaver_flag`. Zoom/scroll over long history; click event → detail. This is the "joined-up view no analyst can assemble by hand."
- Deliverable: `frontend/src/components/Entity360Timeline.tsx`, `frontend/src/components/TimelineEvent.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.388), Part 24.4 (l.950), Part 24.5(a) event shape**.
- Acceptance: txn + access + data + HR/change events render on one ordered timeline; layer/verb encoded visually; off-hours/privileged/leaver flagged; handles long histories. (Inventory items: entity-360 timeline #1,#7; must-cover: entity-360 timeline of txn+access+data+change.)

**FRONTEND-8 — Explanation panel: SHAP, rule provenance, sequence attention, AI narrative**
- What: `src/components/ExplanationPanel.tsx` over `GET /explanations/{alert_id}` + `POST /narratives/{alert_id}`. Sections: (1) **SHAP top contributing features** (horizontal bar chart of `feature` × `contribution`); (2) **rule provenance** — which SoD rule/typology fired (`reason_codes` where `source=rule`, show `code` + `detail`); (3) **sequence attention (LAXCAT)** — per-session/event attention visualization for L4; (4) **graph evidence** (collusion/ring summary from `source=graph`); (5) **AI-generated narrative** — render the `POST /narratives` body, **clearly labelled "AI-generated"**, with a **`tee_attested` badge**, `provider` (near_ai/groq/template), and `attestation_id`. Handle the deterministic-template fallback gracefully (still render; show `tee_attested=false` honestly). Frame everything as **SAR/FMR-defensible**.
- Deliverable: `frontend/src/components/ExplanationPanel.tsx`, `frontend/src/components/ShapChart.tsx`, `frontend/src/components/RuleProvenance.tsx`, `frontend/src/components/AttentionView.tsx`, `frontend/src/components/AiNarrative.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.389), Part 24.4 (l.951), Part 25 (narrative labeling/attestation)**.
- Acceptance: SHAP features chart from real reason codes; rule provenance lists fired SoD/typology codes; attention view renders; narrative shown labelled AI-generated with tee_attested/provider; UI never breaks when narrative degrades to template. (Inventory item: explanation panel #8; must-cover: explanation panel with SHAP + rule-provenance + attention + AI narrative.)

**FRONTEND-9 — Graph/link view: beneficiary networks, shared-identity links, collusion subgraphs**
- What: `src/components/GraphView.tsx` — interactive **Cytoscape.js** subgraph over `GET /entities/{id}/graph`: typed nodes (employees, customers, beneficiaries, devices, accounts) and edges (maker↔checker, shared-device/IP/phone/address, beneficiary links, circular-flow/mule motifs). Highlight **maker-checker collusion subgraphs** and **ring_id** clusters; overlay **GNNExplainer evidence** (which edges/nodes drove the score). Pan/zoom, node-click drill to entity, layout for collusion rings.
- Deliverable: `frontend/src/components/GraphView.tsx`, `frontend/src/components/GraphLegend.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.390), Part 24.4 (l.952)**.
- Acceptance: beneficiary networks, shared-identity links, and maker-checker collusion subgraphs render interactively; ring highlighting works; GNNExplainer evidence overlaid. (Inventory items: graph/link view #9,#16; must-cover: graph/link view.)

**FRONTEND-10 — Peer comparison view**
- What: `src/components/PeerComparison.tsx` over `GET /entities/{id}/peers` — this actor vs **peer group** on the flagged dimension (e.g. off-hours rate, amount z-score, new-beneficiary latency). Box/distribution plots placing the actor against the peer-group distribution; makes "abnormal" concrete and fair (peer-anchored, fairness-aware).
- Deliverable: `frontend/src/components/PeerComparison.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.391), Part 24.4 (l.953)**.
- Acceptance: actor's value plotted against peer-group distribution on the flagged dimension; multiple dimensions selectable. (Inventory item: peer comparison #10; must-cover: peer comparison.)

**FRONTEND-11 — EDD action panel + feedback loop (natural-justice / due-process)**
- What: `src/components/EddActionPanel.tsx` — a **structured EDD checklist** plus actions: **escalate, request-block, close-as-FP, mark-fraud, add-notes, unmask (if permitted)**. Disposition posts to `POST /alerts/{id}/disposition` (`outcome: fraud|false_positive|inconclusive`, `notes`, `evidence_ids[]`) and submits an active-learning label via `POST /feedback`; request-block posts to `POST /alerts/{id}/block-request` (routes to Lead approval — **never auto-block**). Enforce **human-in-the-loop + proportionality** UI gating: no classification without an explicit human action; require notes/evidence for fraud/escalation; show the **immutable-audit confirmation** (`audit_id`, `label_written`, `feedback_queued_for_retraining`) returned by the API. Every disposition becomes a **label** feeding the L3/L4 relabeling loop. Surface the natural-justice posture (explanation shown, proportionate, human decides).
- Deliverable: `frontend/src/components/EddActionPanel.tsx`, `frontend/src/components/EddChecklist.tsx`, `frontend/src/components/AuditConfirmation.tsx`.
- Status: REAL. Blueprint ref: **Part 11 (l.392), Part 24.4 (l.954), Part 24.5(c) disposition, Part 10 (EDD feedback loop), Part 1/Part 0 (natural justice / human-in-the-loop)**.
- Acceptance: all actions present; disposition + feedback POST with correct payload; block-request is a request (no auto-block anywhere); fraud/escalate require notes+evidence; audit_id + label-written + retraining-queued confirmation displayed; SoD/RBAC hides forbidden actions. (Inventory items: EDD loop / relabeling #0, natural-justice workflow #4, action&EDD panel #11, #16; must-cover: EDD checklist + actions (disposition/request-block/notes/unmask).)

### M4 — Role-specialized views and reporting

**FRONTEND-12 — Compliance view: rules/threshold change-control, EWS/RFA coverage, CRILC/FMR export**
- What: `src/views/ComplianceView.tsx` — (1) **configurable rules/thresholds editor** with change-control over `GET/POST/PUT /rules` (propose/edit thresholds; show that changes are four-eyes-approved + audited server-side; show diff/history; Compliance-role-gated); (2) **EWS/RFA indicator-coverage dashboard** (which early-warning/red-flag indicators are covered, gaps); (3) **one-click CRILC/FMR export** via `GET /reports/crilc` + `GET /reports/fmr` (trigger generation, download/preview the regulatory-ready export). RBAC: Compliance Officer (no triage/disposition per matrix).
- Deliverable: `frontend/src/views/ComplianceView.tsx`, `frontend/src/components/RulesEditor.tsx`, `frontend/src/components/EwsCoverage.tsx`, `frontend/src/components/RegulatoryExport.tsx`.
- Status: REAL. Blueprint ref: **Part 24.4 screen 5 (l.956), Part 11 (Reporting l.393), Part 24.2 (/rules, /reports RBAC=Compliance)**.
- Acceptance: rules editor reads/writes /rules with change-control UI + history; EWS/RFA coverage dashboard renders; CRILC and FMR exports trigger and download; all gated to Compliance role. (Inventory items: configurable rules/EWS/exports #2, reporting #12, UI screen 5 #18; must-cover: compliance view (EWS/RFA dashboard, threshold change-control, CRILC/FMR export).)

**FRONTEND-13 — Auditor, model-engineer, admin, and management-KRI reporting views**
- What: four role consoles + reporting:
  - `src/views/AuditorView.tsx` — **read-only immutable audit trail** over `GET /audit?actor=&entity=&from=&to=`, including **who-viewed-which-employee** and **who-closed-what**; filterable; no mutation controls (Auditor = read-only per matrix).
  - `src/views/ModelEngineerView.tsx` — **registry champion/challenger** over `GET /models` + `POST /models/{id}/promote` (promote gated to Model-Eng with sign-off), **drift dashboards** over `GET /drift`, **model-quality metrics** over `GET /metrics/model` — all on **de-identified data only** (no case PII; enforce the matrix's "de-identified only" constraint).
  - `src/views/AdminView.tsx` — **users/roles** over `GET/POST /admin/users`, **rule deployment** surface, **system health** via a **Grafana iframe embed** (port 3000) + `GET /health`/`GET /metrics` (Platform Admin = no case data per matrix).
  - `src/views/ReportingView.tsx` — **management KRI dashboards**, **trend** and **coverage** views, **board-level KRIs** (SCBMF/board): alert-volume vs capacity, MTTD, FPR, SLA/TAT compliance, coverage map; charts via Recharts/visx; reuses CRILC/FMR export entry points.
- Deliverable: `frontend/src/views/AuditorView.tsx`, `frontend/src/views/ModelEngineerView.tsx`, `frontend/src/views/AdminView.tsx`, `frontend/src/views/ReportingView.tsx`, plus `frontend/src/components/{DriftChart,KriDashboard,GrafanaEmbed,AuditTable}.tsx`.
- Status: REAL. Blueprint ref: **Part 24.4 screens 6,7,8 (l.957–959), Part 11 (Reporting l.393), Part 24.2 (/audit, /models, /drift, /metrics/model, /admin/users RBAC), Part 23.2 (registry layout context)**.
- Acceptance: auditor view read-only shows who-viewed-whom + who-closed-what; model-engineer view shows registry/drift/metrics on de-identified data and gates promote; admin view manages users/roles + rule deployment + embeds Grafana health; reporting view renders KRI/trend/coverage incl. board KRIs; every view RBAC-gated to its role. (Inventory items: risk dashboards/coverage/board-KRIs #3, reporting #12, UI screens 6/7/8 #19,#20,#21; must-cover: auditor view, model-engineer view, admin view, reporting/KRI dashboards.)

---

## 7. Detailed build instructions per milestone (blueprint specifics — nothing lost)

### M1 specifics
- **OIDC (FRONTEND-2):** Authorization-Code + **PKCE** against Keycloak 25.x (issuer on :8080, realm/client provisioned by PLATFORM/BACKEND — read the client-id/issuer URL from env, never hardcode). Tokens are **short-lived JWTs**; keep the access token **in memory**, refresh via `POST /auth/refresh` before expiry; never persist to localStorage. MFA is enforced by the IdP — your UI surfaces the redirect/step, it does not implement factors. Session controls: idle-timeout logout, refresh-on-activity, explicit logout that clears state and revokes.
- **RBAC matrix (FRONTEND-3) — encode the Part 24.1 table exactly.** The 9 capabilities are: *View alerts · Triage/assign · Disposition · Request block · Unmask PII · Tune rules/thresholds · Train/deploy models · View audit log · Admin*. The 8 roles and their cells (✅ / ❌ / ⚠️):
  - **Analyst (L1):** view (assigned only) ✅, triage ✅, disposition ✅, request-block ✅(request), unmask ⚠️(case-scoped, logged), tune-rules ❌, train/deploy ❌, audit ❌, admin ❌.
  - **Senior Investigator:** view (all) ✅, triage ✅, disposition ✅, request-block ✅, unmask ✅(logged), tune ❌, train ❌, audit (view own), admin ❌.
  - **Team Lead/MLRO:** view ✅, triage ✅, disposition ✅(override), request-block ✅(approve), unmask ✅(logged), tune ⚠️(propose), train ❌, audit ✅, admin ❌.
  - **Compliance Officer:** view ✅, triage ❌, disposition ❌, request-block ❌, unmask ✅(logged), tune ✅(change-controlled), train ❌, audit ✅, admin ❌.
  - **Auditor:** view ✅(read-only), triage ❌, disposition ❌, request-block ❌, unmask ❌, tune ❌, train ❌, audit ✅(full), admin ❌.
  - **Model Engineer/Data Scientist:** view ⚠️(de-identified only), triage ❌, disposition ❌, request-block ❌, unmask ❌, tune ❌, train ✅(with sign-off), audit (view own), admin ❌.
  - **Platform Admin:** view ❌(no case data), triage ❌, disposition ❌, request-block ❌, unmask ❌, tune ❌, train ⚠️(deploy infra), audit ✅, admin ✅.
  - **Service accounts:** scoped tokens; audit write-only; everything else ❌.
  - Render UI controls strictly per these cells; treat ⚠️ as "available but constrained/logged" and reflect the constraint in the UI (e.g., de-identified data, case-scoped unmask, change-controlled rule edits). The server is authoritative; the UI guard is defense-in-depth.
- **SoD (Part 19.6):** model deployer cannot label/close own alerts; investigator cannot tune the rules generating their own alerts. Hide those controls contextually.
- **PII default-mask:** `pii_tokenized:true` alerts show tokens (`EMP-7f3a`, `ACCT-4d22`, `BEN-9b1c`); `<MaskedPII>` exposes unmask only where the matrix allows, calling `POST /entities/{id}/unmask` (audited).

### M2 specifics
- **Triage ranking (FRONTEND-4):** composite priority = function of `risk_score` (0–100) × `exposure_inr` (monetary) × `confidence` (0–1). Surface the composite; allow sort by each. **Dedup per entity_id** — collapse repeat alerts for the same actor into one row (with a count + drill to all). **SLA/TAT timer** from `sla_due_ts` (RBI ≤30-day examination window); color-grade (green → amber → red → breached); live update.
- **Worked burst (Part 24.5(d)) as a fixture:** ensure the triage queue + alert detail correctly render the worked example: alert `alr_3d7e22`, entity `EMP-7f3a`, risk 87/high/0.82, contributing_layers `[L1_rules, L2_unsupervised, L3_gbdt, L5_graph]`, reason codes (NEW_BENEFICIARY_THEN_HIGHVALUE, OFF_HOURS_ACTIVITY, SHAP `new_beneficiary_to_payment_latency_min`/`maker_checker_pair_frequency_30d`, graph ring RNG-12), exposure ₹48,00,000, SLA 2026-07-30. Use this as an MSW fixture and an e2e assertion.

### M3 specifics
- **Entity-360 timeline (FRONTEND-7):** one ordered timeline of the four event families (transactions / access / data-layer / change-HR) from the L0 event model; encode `context.layer`, `action.verb`, `action.maker_checker`, and flag `is_off_hours`/`privileged_flag`/`leaver_flag`. Long-history scroll/zoom.
- **Explanation (FRONTEND-8):** SHAP bars (sorted by |contribution|); rule provenance maps each `rule` reason code to the SoD/typology it came from; LAXCAT attention over the session sequence; graph evidence summary; AI narrative **clearly labelled**, with `tee_attested` badge, `provider`, `attestation_id`. Defensible-for-SAR/FMR framing. If `provider=template` (deterministic fallback) or `tee_attested=false`, render honestly without breaking.
- **Graph (FRONTEND-9):** Cytoscape typed graph; highlight maker-checker collusion + ring_id; GNNExplainer overlay.
- **Peer (FRONTEND-10):** distribution/box plot, actor marker vs peer group on the flagged dimension.
- **EDD (FRONTEND-11):** structured checklist; actions escalate/request-block/close-FP/mark-fraud/notes/unmask; disposition `{outcome, notes, evidence_ids}` → expect `{status, label_written, feedback_queued_for_retraining, audit_id}`; **request-block never blocks** (routes to Lead); require notes+evidence for fraud/escalation; show audit confirmation; every disposition = a label into the relabeling loop (Part 10). Natural-justice: explanation visible, proportionate, human decides — surface this.

### M4 specifics
- **Compliance (FRONTEND-12):** rules/threshold editor with change-control + history (four-eyes is enforced server-side; UI shows pending-approval state); EWS/RFA coverage dashboard; CRILC (3-crore/7-day, 180-day window context) + FMR one-click export.
- **Auditor (FRONTEND-13):** read-only `GET /audit` incl. **who-viewed-whom** and who-closed-what; no mutations.
- **Model Engineer (FRONTEND-13):** registry champion/challenger (`GET /models`, gated `POST /models/{id}/promote`), drift dashboards (`GET /drift`), model-quality metrics (`GET /metrics/model`) — **de-identified data only**.
- **Admin (FRONTEND-13):** users/roles (`/admin/users`), rule deployment, **Grafana iframe embed** (:3000) + `GET /health`/`GET /metrics`.
- **Reporting (FRONTEND-13):** management KRI dashboards, trend + coverage views, board-level KRIs (alert-volume-vs-capacity, MTTD, FPR, SLA/TAT compliance, coverage map) for SCBMF/board.

---

## 8. Testing & all checks (commands + what must pass)

Run all from `frontend/`. CI (owned by PLATFORM) will run these; you must keep them green locally.

| Check | Command | Must pass |
|---|---|---|
| Install (pinned) | `npm ci` | lockfile resolves to pinned versions |
| Type-check | `npx tsc --noEmit` | zero type errors |
| Lint | `npx eslint . --max-warnings=0` | zero errors/warnings |
| Format | `npx prettier --check .` | all files formatted |
| Unit/component tests | `npx vitest run` | all pass; cover apiClient, RBAC guards, SLA timer, dedup/ranking logic, `<MaskedPII>`, EDD payload assembly, reason-code rendering |
| Contract tests | `npx vitest run --dir src/__contract__` | every component renders the **BACKEND.md / Part 24.5 sample payloads** without error (event, alert, disposition, narrative memo, explanations) |
| e2e (Playwright) | `npx playwright test` | login→triage→claim→alert-detail→entity360→explanation→graph→peer→disposition flow; the **worked burst (Part 24.5(d))** end-to-end; RBAC: a forbidden route/control is absent per role |
| Build | `npm run build` | production build succeeds |
| a11y smoke | Playwright + axe in e2e | no critical a11y violations on core screens |
| Bundle/perf budget | Vite build report | triage queue virtualized; initial route bundle within budget; **drill-down feels sub-second** (Part 11) against mocked latency |

**Domain-specific test requirements:**
- **RBAC tests:** parametrized over all 8 roles — assert each of the 9 capabilities' controls is present/absent per the Part 24.1 matrix (incl. ⚠️ constraints). Assert SoD (deployer can't close own alert; investigator can't tune own-alert rules).
- **Alert-only invariant test:** assert there is **no UI path** that blocks money or classifies without an explicit human action; `block-request` only issues a request.
- **PII test:** default render shows tokens; unmask only appears for permitted roles and calls `/entities/{id}/unmask`.
- **Narrative-degradation test:** when `/narratives` returns `provider=template`/`tee_attested=false`, the panel still renders and labels it correctly; when the call errors, UI does not break.
- **SLA test:** timer warns/breaches correctly relative to `sla_due_ts`.

**Definition of Done per milestone:** (M1) app boots, SSO works, RBAC guards + masked-PII verified against Part 24.1; (M2) triage ranks/dedups/SLAs + case mgmt; (M3) all five detail sub-panels render real reason codes + disposition writes a label with audit confirmation; (M4) all four role consoles + reporting RBAC-gated and bound to the right routes. Each milestone: all §8 checks green, `TODO.md` rows `[x]`, laptop-log entry with blueprint validations, §9 gate satisfied.

---

## 9. Blueprint validation gate (each requirement you own → covered)

Before marking the workstream done, confirm every row maps to a built, validated task. (Self-check: this table must have no uncovered row.)

| Blueprint requirement | Part (line) | Covered by |
|---|---|---|
| Triage queue: ranked by fused risk×exposure×confidence, deduped per entity, SLA/TAT timer | 11 (l.387), 24.4 (l.947) | FRONTEND-4 |
| Entity-360: txn + access + data + HR/change on one timeline | 11 (l.388), 24.4 (l.950) | FRONTEND-7 |
| Explanation panel: SHAP + rule provenance + sequence attention + graph evidence + AI narrative | 11 (l.389), 24.4 (l.951), 25 | FRONTEND-8 |
| Graph/link view: beneficiary networks, shared-identity links, maker-checker collusion subgraphs | 11 (l.390), 24.4 (l.952) | FRONTEND-9 |
| Peer comparison vs peer group on flagged dimension | 11 (l.391), 24.4 (l.953) | FRONTEND-10 |
| Action & EDD: escalate/request-block/close-FP/mark-fraud/notes + EDD checklist; every action a label → immutable audit | 11 (l.392), 24.4 (l.954) | FRONTEND-11 |
| Reporting: one-click CRILC/FMR export + management KRI + trend/coverage (board/SCBMF) | 11 (l.393), 24.4 (l.956) | FRONTEND-12, FRONTEND-13 |
| Stack: React+TS over ClickHouse-backed API; Grafana for ops | 11 (l.395), 24.3 | FRONTEND-1, FRONTEND-13 (Grafana embed) |
| Screen 1 Login/SSO: OIDC redirect, MFA, session controls | 24.4 (l.946) | FRONTEND-2 |
| Screen 2 Triage queue (Analyst home): filters, SLA timer, one-click claim, dedup | 24.4 (l.947) | FRONTEND-4 |
| Screen 3 Alert/Case detail: header + entity-360 + explanation(AI narrative) + graph + peer + EDD | 24.4 (l.948–954) | FRONTEND-6,7,8,9,10,11 |
| Screen 4 Case management: assignment, status, linked alerts, notes, history | 24.4 (l.955) | FRONTEND-5 |
| Screen 5 Compliance: EWS/RFA dashboard, threshold/rule change-control, CRILC/FMR export | 24.4 (l.956) | FRONTEND-12 |
| Screen 6 Auditor: read-only immutable audit incl. who-viewed-whom, who-closed-what | 24.4 (l.957) | FRONTEND-13 |
| Screen 7 Model engineer: registry champion/challenger, drift, model-quality on de-identified data | 24.4 (l.958) | FRONTEND-13 |
| Screen 8 Admin: users/roles, rule deployment, system health (Grafana embed) | 24.4 (l.959) | FRONTEND-13 |
| RBAC: 8 roles × 9 capabilities; gate every view; unmask = separate audited permission | 24.1 (l.874–888) | FRONTEND-3 (+ enforced across all views) |
| SoD rule: deployer can't label/close own; investigator can't tune own-alert rules | 24.1/19.6 (l.888) | FRONTEND-3, FRONTEND-11, FRONTEND-12 |
| Render exact sample payloads (event, alert, disposition, worked burst) | 24.5 (l.961–1026) | FRONTEND-1 (types), FRONTEND-4/6/7/8/11 (render), §8 contract+e2e |
| Natural-justice / due-process: proportionality, explanation, human-in-the-loop before classification | 0/1/2 (l.17,19,50,68), 11 | FRONTEND-8, FRONTEND-11 |
| EDD feedback loop: every disposition relabels L3/L4 | 0/1/10 (l.17,19,50) | FRONTEND-11 |
| All actions call BACKEND APIs from BACKEND.md; alert-only, never auto-block | 24.2, golden rules | all tasks; §8 alert-only invariant test |

---

## 10. Definition of Done & handoff

**The FRONTEND workstream is DONE when:**
1. All 13 tasks built, REAL, on synthetic/mock data; every §9 gate row covered and validated against its blueprint Part.
2. All §8 checks green (`tsc`, eslint, prettier, vitest unit+contract, Playwright e2e incl. worked-burst + RBAC matrix + alert-only invariant, build, a11y, perf budget).
3. Every screen RBAC-gated per Part 24.1; PII tokenized by default with audited unmask; **no UI path auto-blocks or auto-classifies** (alert-only).
4. Every API call binds to a `BACKEND.md` route (no invented fields); where the backend isn't ready, an MSW mock against the Part 24.5 shapes is in place behind `VITE_USE_MOCKS`, logged as a stub.

**Handoff / MD updates (do these at the end and continuously):**
- **`TODO.md`** — set FRONTEND M1–M4 rows to `[x]` only when blueprint-validated; record any blockers in §7 (mirror in CONTEXT.md).
- **`CONTEXT.md`** — append integration-log entries (newest first) for: the app/port (Vite :5173), any query params or fields you needed from BACKEND (tagging BACKEND), the `tee_attested` badge convention, the unmask-is-audited UI contract, and any deviation.
- **`docs/laptops/04-frontend.md`** — keep current: files created, decisions, **blueprint validations per task (task → Part → how verified)**, deviations + rationale, stubs created for not-yet-built backend endpoints, blockers.
- **Integration test with other parts:** coordinate with PLATFORM's cross-workstream integration-test harness + CI; run the full vertical slice (PLATFORM compose up → DATA simulator burst → BACKEND L1/fusion → ML score → BACKEND `/alerts` → **your triage queue → alert detail → disposition → audit**). Confirm the worked burst (Part 24.5(d)) renders end-to-end. Verify RBAC against BACKEND's real enforcement (your client guard is defense-in-depth; the server is authoritative).
- **Do NOT** edit `BACKEND.md` or any non-`frontend/` directory; propose contract needs in `CONTEXT.md`.

> Build the thin vertical slice first (login → triage → one alert detail → disposition) so a synthetic fraud burst becomes a visible, dispositionable alert as early as possible (BUILD_PLAN "Slice 0"), then deepen each panel. Validate every step against the blueprint. Nothing dropped. Stay in lane.
