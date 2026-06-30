# Laptop 04 — FRONTEND — Working Log

> Your **own** file. Record decisions, files created, blueprint validations, deviations, and blockers. Full brief: [prompts/04_FRONTEND.md](../../prompts/04_FRONTEND.md). Contract: [BACKEND.md](../../BACKEND.md).

## Status

- Branch: `hawk-eye/frontend` · Owns: `frontend/`
- **M1–M4 built, REAL, all §8 gates green.** `tsc` 0 errors · `eslint --max-warnings=0` clean · `prettier --check` clean · `vitest` 112 passing (unit + component + contract) · Playwright e2e 3 passing (worked burst + RBAC + alert-only) · `vite build` succeeds · a11y nested-interactive fixed.
- The console runs end-to-end on MSW mocks (`VITE_USE_MOCKS=true`) with **no backend**, rendering the Part 24.5 worked burst (`alr_3d7e22` / `EMP-7f3a` / ring `RNG-12` / ₹48,00,000).

## Decisions

- **Single seam = `src/lib/apiClient.ts`** — one typed method per `BACKEND.md` §3 route. Components never call `fetch`; flipping mock↔real is the `VITE_USE_MOCKS` flag. `src/lib/types.ts` mirrors `BACKEND.md` field-for-field for the byte-specified contracts (event/alert/disposition/narrative) and adds clearly-marked `[FE-proposed]` shapes for endpoints BACKEND.md lists by route but not yet by body.
- **JWT kept in memory** (`src/lib/authToken.ts`), never localStorage (security posture). OIDC `User` stored in an in-memory store; only the transient PKCE state uses sessionStorage. A reload deliberately drops the token.
- **RBAC matrix encoded exactly** (`src/auth/capabilities.ts`) as the Part 24.1 8×9 table with ⚠️ constraints + view scopes; drives every route guard (`RoleShell`) and control (`useAuth().can`). Server is authoritative; client guard is defense-in-depth. SoD (Part 19.6) via `violatesSoD`.
- **Design system**: hand-authored shadcn-style primitives (Radix + CVA + tailwind-merge) in `src/components/ui/` so components live in-repo and the build is deterministic. Dark-first token palette with domain colours (severity / SLA bands / reason-code provenance / AI·TEE).
- **Charts** = Recharts; **graph** = Cytoscape.js (mounted via ref, no `react-cytoscapejs`); **OIDC** = oidc-client-ts. Mocking = MSW (worker in `public/`).
- **Build orchestration**: foundation (libs/auth/app-shell/design-system) hand-authored for coherence; the 13 task deliverables (views + panels) built by 10 parallel sub-agents against a precise foundation contract, then integrated (tsc/lint/build/test) to green.

## Files created (high level)

- `frontend/` Vite+React19+TS5.6 project (configs: vite/vitest, tailwind3, postcss, eslint10 flat, prettier, playwright, tsconfig{,.node,.e2e}, `.env.{example,development,production}`).
- `src/lib/`: `types.ts`, `apiClient.ts`, `http.ts`, `authToken.ts`, `env.ts`, `format.ts`, `cn.ts`, `queryKeys.ts`, `mocks/{fixtures,handlers,browser,server,enable}.ts`.
- `src/auth/`: `capabilities.ts`, `rbac.tsx`, `session.ts`, `oidc.ts`, `AuthProvider.tsx`, `LoginPage.tsx`, `CallbackPage.tsx`, `RoleShell.tsx`.
- `src/app/`: `Providers`, `AppLayout`, `Sidebar`, `Topbar`, `IstClock`, `router`, `nav-config`, `Dashboard`, `Forbidden`, `NotFound`, `ErrorBoundary`; `src/App.tsx`, `src/main.tsx`, `src/index.css`.
- `src/components/`: `ui/*` (button, card, badge, input, label, textarea, select, checkbox, switch, tabs, dialog, tooltip, dropdown-menu, separator, avatar, scroll-area, popover, table, skeleton, spinner, empty-state, toaster); shared `badges`, `MaskedPII`, `SlaTimer`, `PageHeader`, `QueryBoundary`; the panels `AlertRow`, `AlertHeader`, `Entity360Timeline`, `TimelineEvent`, `ExplanationPanel`, `ShapChart`, `RuleProvenance`, `AttentionView`, `AiNarrative`, `GraphView`, `GraphLegend`, `PeerComparison`, `EddActionPanel`, `EddChecklist`, `AuditConfirmation`, `CaseNotes`, `CaseHistory`, `RulesEditor`, `EwsCoverage`, `RegulatoryExport`, `AuditTable`, `DriftChart`, `KriDashboard`, `GrafanaEmbed`.
- `src/views/`: `TriageQueue`, `AlertDetail`, `CaseManagement`, `CaseDetailShell`, `ComplianceView`, `AuditorView`, `ModelEngineerView`, `AdminView`, `ReportingView`.
- Tests: `src/auth/capabilities.test.ts`, `src/lib/format.test.ts`, `src/components/{MaskedPII,SlaTimer}.test.tsx`, `src/__contract__/{payloads,render}.contract.test.*`, `e2e/investigator.e2e.ts`, `src/test/{setup,utils}.tsx`.

## Blueprint validation (task → Part → how verified)

| Task | Part | Verified |
|---|---|---|
| FRONTEND-1 scaffold + typed client | 11, 24.3, 24.5 | App boots :5173; `apiClient` method per BACKEND.md route; MSW serves Part 24.5 alert/event/disposition; `build` + `tsc` clean. |
| FRONTEND-2 Login/SSO | 24.4 s1, 24.1 | OIDC PKCE (oidc-client-ts) + mock persona SSO; JWT in memory; idle-logout + refresh-before-expiry; e2e logs in. |
| FRONTEND-3 RBAC + MaskedPII | 24.1, 19.6, 25.3 | `capabilities.test.ts` asserts all 72 cells + ⚠️ + scopes + SoD vs an independent Part 24.1 truth table; `MaskedPII.test` proves default-mask + audited unmask gating; e2e proves forbidden routes/nav. |
| FRONTEND-4 Triage queue | 11 l387, 24.4 s2, 24.5b | Ranked by `compositePriority` (risk×exposure×confidence), dedup per entity, 4 filters, virtualized, SLA timer, one-click claim; worked burst on top; e2e + format tests. |
| FRONTEND-5 Case management | 24.4 s4 | List/assign/status-workflow/linked-alerts/notes/history over `/cases` (FE-proposed). |
| FRONTEND-6 Alert detail + header | 24.4 s3, 24.5b | Header renders sample-alert fields (render-contract test: risk 87, EMP-7f3a, ₹48,00,000); tabs mount the 5 sub-panels + sticky EDD rail. |
| FRONTEND-7 Entity-360 timeline | 11 l388, 24.4, 24.5a | One timeline of txn/access/data/change; layer/verb encoded; off-hours/privileged/leaver flagged; contract test asserts evt_8f2a1c90 groups. |
| FRONTEND-8 Explanation panel | 11 l389, 24.4, 25 | SHAP bars + rule provenance + LAXCAT attention + graph evidence + AI narrative (labelled, TEE badge, provider); render-contract proves rule code + AI label + template degradation (tee_attested=false). |
| FRONTEND-9 Graph/link view | 11 l390, 24.4 | Cytoscape subgraph; maker-checker collusion + ring RNG-12 highlight; GNNExplainer overlay; legend. |
| FRONTEND-10 Peer comparison | 11 l391, 24.4 | Actor vs peer-group distribution (box/scatter) on the flagged dimension; selectable dimensions. |
| FRONTEND-11 EDD action panel | 11 l392, 24.4, 24.5c, 10, 0/1 | Checklist + actions; disposition+feedback POST; **request-block routes to Lead, never auto-blocks**; notes+evidence required for fraud/escalate; audit_id + label-written + retraining confirmation; SoD hides controls; render-contract proves alert-only + SoD. |
| FRONTEND-12 Compliance view | 24.4 s5, 24.2 | Rules change-control (four-eyes → pending_approval) + history; EWS/RFA coverage; one-click CRILC/FMR export with download. |
| FRONTEND-13 Auditor/Model/Admin/Reporting | 24.4 s6-8, 23.2 | Read-only audit (who-viewed-whom); registry/drift/quality de-identified + gated promote; users/roles + Grafana embed; board/SCBMF KRIs. |
| Render exact sample payloads | 24.5 | `payloads.contract.test` + `render.contract.test` + e2e worked burst. |
| Alert-only / never auto-block | golden rules | render-contract + e2e assert only "Request block" (routed to Lead); no block-money path. |

## Deviations / assumptions

- **Vite 8 + @vitejs/plugin-react 6 (not "Vite 5.x")** — the prompt's BOM predates current toolchain; plugin-react 6 requires Vite 8, and Node 22/26 needs a modern Vite. Part 24.3 says "verify latest patch… not gospel". Pinned: React 19.2.7, TS 5.6.3, Tailwind 3.4.19, Vitest 4.1.9, ESLint 10 (flat), RR 7.18.1, TanStack Query 5 / Table 8 / Virtual 3, Recharts 3, Cytoscape 3.34, oidc-client-ts 3.5, MSW 2.14, Playwright 1.61.
- **Tailwind 3.4 (not 4.x)** for shadcn-style reliability/determinism. **shadcn/ui hand-authored** (it's a copy-in CLI, not a dep).
- `manualChunks` written in **function form** (Rolldown in Vite 8 rejects the object form).
- **Cases derived as alert groupings** — `/cases*` is `[FE-proposed]` (not in BACKEND.md §3 yet).

## Stubs created (not-yet-built backend) → see CONTEXT.md, tagged BACKEND

- Render shapes for endpoints BACKEND.md lists by route but not by body: `/explanations`, `/entities/{id}` + `/timeline` + `/graph` + `/peers`, `/rules`, `/models` + `/drift` + `/metrics/model`, `/audit`, `/admin/users`, `/reports/fmr|crilc`. All served by MSW against the Part 24.5 shapes behind `VITE_USE_MOCKS`.
- New routes proposed (FE-proposed, flagged to BACKEND): `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/{status,assign,notes}`, `GET /reports/ews-coverage`, `GET /reports/kris`.

## Blockers (mirror in TODO.md §7 + CONTEXT.md)

- None blocking. Awaiting BACKEND to finalise the `[FE-proposed]` response bodies + the `/cases`, `/reports/ews-coverage`, `/reports/kris` routes; until then MSW mocks stand in (one switch to real). Verify RBAC against BACKEND's real enforcement during the cross-WS integration slice (PLATFORM harness).

## Session log (newest first)

- **2026-06-30** — Built the full FRONTEND workstream (M1–M4, all 13 tasks REAL). Foundation hand-authored; 13 task deliverables via 10 parallel sub-agents; integrated to green. All §8 checks pass (tsc/eslint/prettier/vitest 112/Playwright e2e 3/build/a11y). Worked burst renders end-to-end on mocks. Pushed to `hawk-eye/frontend`.
