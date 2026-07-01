# OWNERSHIP.md — UI uplift file ownership (A / B / C)

> Disjoint ownership → clean parallel merges (the repo's "laptop" model). Work only on your branch;
> pull before you write; edit only files in your area (+ your log + _appends_ to shared docs).

## Agent A — `hawk-eye/ui-foundation` (design system, theme, motion, shell, primitives)

**Owns / edits:**

- `frontend/src/ui/**` — the new design-system dir (signature primitives, motion, tokens helpers, gallery).
- `frontend/src/index.css`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js` — theme/tokens/global styles.
- `frontend/index.html` — root class / meta (theme default).
- App **shell/chrome**: `frontend/src/components/layout/**`, `frontend/src/components/command/**` (sidebar, topbar, ⌘K, env banner).
- `docs/ui/UI_UPLIFT.md` (**A owns**), `docs/laptops/ui-foundation.md` (A's log).
- Adds one route to `frontend/src/app/router.tsx` for `/ui-gallery` (coordinate; keep the diff to that one line).
  **Does NOT touch:** feature screens (`src/views/**`, most of `src/components/**` domain widgets) — that's B; the CI/verification harness — that's C.

## Agent B — `hawk-eye/ui-features` (feature screens, data-rich views)

**Owns / edits:** `frontend/src/views/**`, feature/domain components under `frontend/src/components/**`
(triage rows, entity-360, explanation panel, graph, EDD, compliance, auditor, model-eng, admin,
reporting), their tests, `docs/laptops/ui-features.md`. **Consumes** A's kit via `@/ui`; if a primitive
is missing, request it in `UI_UPLIFT.md` (tag `[A]`) and stub locally behind the agreed API until it lands.
**Does NOT touch:** `src/ui/**`, theme/tokens/Tailwind, shell chrome, the harness.

## Agent C — `hawk-eye/ui-integrity` (gates, a11y, invariants, fixing)

**Owns / edits:** `.github/workflows/**` (frontend CI), test infra/config (`vitest`/`playwright`/`eslint`/
`prettier`/`tsconfig`), a11y + bundle checks, invariant-guard tests, `docs/ui/INTEGRITY.md`,
`docs/laptops/ui-integrity.md`. **Floating fixer:** may surgically fix a clearly-blocking breakage in
A's/B's files, then log it in `INTEGRITY.md` and tag the owner (prefer a logged patch over a silent overwrite).

## Shared (append-only): `CONTEXT.md`, `TODO.md §7`, `docs/ui/UI_UPLIFT.md` (read), `docs/ui/OWNERSHIP.md` (this).
