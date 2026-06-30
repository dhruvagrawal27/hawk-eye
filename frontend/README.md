# Hawk-Eye — Investigator Console (FRONTEND)

The React + TypeScript investigator dashboard for the Hawk-Eye insider & privileged-user fraud-detection platform (blueprint **Part 11** and **Part 24.4**). A **thin client** over the BACKEND REST API (`BACKEND.md`), it lets the fraud team **triage → investigate → explain → act** on insider-fraud alerts, plus the role-specialized compliance / auditor / model-engineer / admin / reporting consoles.

> **Alert-only.** The UI never auto-blocks money or auto-classifies — a human always decides. **On-prem + synthetic only.** Tokenized PII by default; unmask is an audited backend call. Every view is RBAC-gated.

## Quick start

```bash
npm ci
npm run dev          # http://localhost:5173 — runs fully on MSW mocks (VITE_USE_MOCKS=true in dev)
```

In dev the console runs with **no backend**: Mock Service Worker serves the Part 24.5 sample payloads (the worked burst `alr_3d7e22` / `EMP-7f3a` / ring `RNG-12`). Sign in by picking a demo persona (Analyst, Senior, MLRO, Compliance, Auditor, Model Engineer, Admin) to inspect RBAC end-to-end. Switch role any time from the top bar.

To run against the real BACKEND, set `VITE_USE_MOCKS=false` and the `VITE_*` URLs (see `.env.example`); the typed `apiClient` is the single seam, so mock↔real is one flag.

## Scripts

| Script | What |
|---|---|
| `npm run dev` | Vite dev server on :5173 (mocks on) |
| `npm run build` | `tsc --noEmit` + production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` / `lint:fix` | ESLint (flat config), zero-warning gate |
| `npm run format` / `format:check` | Prettier |
| `npm test` | Vitest unit + component + contract |
| `npm run test:contract` | Contract tests against the Part 24.5 payloads |
| `npm run e2e` | Playwright (worked-burst flow + RBAC + alert-only invariant) |

## Architecture

```
src/
  lib/          types (BACKEND.md mirror) · apiClient (one method per route) · http · format (IST/INR/SLA) · mocks (MSW + fixtures)
  auth/         capabilities matrix (Part 24.1) · rbac guards · OIDC/PKCE · session controls · LoginPage · RoleShell · MaskedPII
  app/          providers · layout · sidebar/topbar · router (RBAC-gated) · dashboard
  components/   design system (ui/) · domain badges · SlaTimer · the alert/explanation/graph/peer/EDD panels
  views/        the 8 screens (triage, alert detail, cases, compliance, auditor, model-engineer, admin, reporting)
```

The **single seam** is `src/lib/apiClient.ts` — components call it (never `fetch`), and it binds 1:1 to the `BACKEND.md` route table. See `docs/laptops/04-frontend.md` for the build log and `CONTEXT.md` for cross-workstream notes (FE-proposed render shapes for under-specified endpoints are flagged there for BACKEND).

## Stack

React 19 · TypeScript 5.6 · Vite 8 · TanStack Query/Table/Virtual · React Router 7 · Tailwind 3 + shadcn-style UI (Radix) · Recharts · Cytoscape.js · oidc-client-ts (Keycloak) · MSW · Vitest + Testing Library · Playwright. Versions pinned in `package.json` + lockfile (blueprint Part 24.3 BOM; deviations noted in the laptop log).
