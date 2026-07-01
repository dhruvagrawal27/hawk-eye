# INTEGRITY.md — live gate status & breakage log (Agent C · `hawk-eye/ui-integrity`)

> The single source of truth for the frontend floor during the Daylight-Forensics UI uplift. A and B
> move fast; C keeps the floor from collapsing. This board reports **red/green per gate**, every
> breakage caught (file · cause · owner), each fix or owner-tagged patch, and every safety-invariant
> risk. Keep it current so A and B always know the floor state. Owned by C; append-friendly.

_Baseline reference: `GETTING_STARTED.md §8` = "112 passed +3 browser e2e". The uplift may only ever
**raise** these — never drop them (invariant #8)._

---

## 1. Gate status (last verified on `hawk-eye/ui-integrity` against the integrated working tree)

| Gate | Cmd | Status | Notes |
|---|---|---|---|
| Types | `tsc --noEmit` (strict) | 🟢 | 0 errors |
| Lint | `eslint . --max-warnings=0` | 🟢 | 0 warnings; harness scripts get a Node-globals block |
| Format | `prettier --check .` | 🟢 CI / ⚠ local | Green on CI (LF). Windows local shows CRLF false-positives — fixed by `frontend/.gitattributes` (added) + `git add --renormalize .`. See §5. |
| Unit | `vitest run` | 🟢 | **198 passed** (≥112 floor); +26 from C's invariant guards |
| Test-count floor | `node scripts/check-test-count.mjs` | 🟢 | asserts ≥112 + zero failures + 8 guard files present |
| Build | `vite build` | 🟢 | production build OK |
| Bundle budget | `node scripts/check-bundle-size.mjs` | 🟢 | initial ≈353 KB gz (budget 500), total JS ≈764 KB gz (budget 1100) |
| e2e count | `node scripts/check-e2e-count.mjs` | 🟢 | **7** e2e (≥3 floor) |
| e2e (browser) | `playwright test` | 🟢 CI | runs in CI (chromium); local needs `npm run e2e:install` |

**One-command floor check:** `cd frontend && node scripts/verify.mjs` (add `--e2e` to include the browser slice).

> Counts move as A and B add tests in parallel — they only go up. The floor gate enforces the ≥112 / ≥3
> contract, not a frozen number.

---

## 2. What C shipped (the verification harness)

- **Frontend CI** — `.github/workflows/frontend-ci.yml`. The repo's `ci.yml` covers Python/platform but
  had **no frontend gate**; this is it. Two jobs (`gates`, `e2e`), path-filtered to `frontend/**`,
  blocking a merge that drops the test count, breaks the build, blows the bundle budget, fails a11y, or
  trips an invariant guard.
- **Local harness** — `frontend/scripts/`: `verify.mjs` (all gates, one command),
  `check-test-count.mjs` (≥112 + guard-presence), `check-bundle-size.mjs` (gzip budgets),
  `check-e2e-count.mjs` (≥3).
- **Durable safety-invariant guards** — `frontend/src/__invariants__/` (8 files, 26 tests). These are
  the *point of the product*; they must keep passing after the uplift:

  | Guard | Invariant | How it protects |
  |---|---|---|
  | `alert-only.invariant.test.ts` | #1 alert-only | apiClient has `blockRequest`, no auto-block/classify method or route; static source scan bans auto-block/classify affordances |
  | `contestability.invariant.test.tsx` | #2 contestability | explanation reason codes always render; a no-explanation alert shows an explicit invalid state (retry), never blank |
  | `audited-unmask.invariant.test.tsx` | #3 watch-the-watchers | unmask fires `POST /entities/{id}/unmask` and shows the "logged" cue; no unmask affordance for roles without `unmask_pii` |
  | `rbac-routes.invariant.test.ts` | #4 RBAC/SoD | router `ROUTE_ROLES` + sidebar `NAV_ITEMS` never widen past the MATRIX (no case-data leak, cap-gated routes, admin=it_admin, no service_account) |
  | `no-secrets.invariant.test.ts` | #5 no client secrets | `import.meta.env` only in the env seam; no PEM key / literal JWT / hardcoded secret |
  | `contract-routes.invariant.test.ts` | #6 data contract | every apiClient route ∈ `backend/openapi.json` ∪ the documented `[FE-proposed]` allowlist — invents nothing |
  | `mocks-intact.invariant.test.ts` | #5/#6 MSW mocks | MSW server + handler set stay wired and cover the worked-burst routes |
  | `reduced-motion.invariant.test.tsx` | #7 reduced motion | core alert surface fully renders/usable with `prefers-reduced-motion: reduce` |

- **a11y / reduced-motion e2e** — `frontend/e2e/a11y.e2e.ts` (Playwright, `reducedMotion: 'reduce'`):
  usable + keyboard-reachable under reduced motion.
- **Line-ending policy** — `frontend/.gitattributes` (LF) so the format gate is consistent across OSes.
- **ESLint config** — added a Node-globals block for `scripts/**` (harness scripts are plain ESM).

---

## 3. Breakage log (every red state caught → resolution)

Newest first. Owner tags: **[A]** foundation, **[B]** features, **[C]** integrity.

- **2026-07-01 · `tsc` RED → resolved by owner (~1 min)** — `frontend/src/ui/PeerStrip.tsx:36`
  `TS5076: '||' and '??' operations cannot be mixed without parentheses`. Owner **[A]** (design-system
  dir). Caught during C's baseline verification while A was actively writing `src/ui/`. Per the fix
  mandate (owner actively editing → do not overwrite), C did **not** touch the file; A self-corrected on
  the next save and `tsc` returned to 🟢. No patch needed. _Signal value: the integrity monitor caught a
  real red gate the moment it appeared._
- **2026-07-01 · `eslint .` RED → fixed by C** — `frontend/scripts/*.mjs`: `no-undef` on
  `console`/`process`. Cause: the flat config's globals block only targeted `**/*.{ts,tsx}`, so C's own
  ESM harness scripts had no Node globals. Owner **[C]**. Fixed in `eslint.config.js` (added a
  `scripts/**` block with `globals.node`). 🟢.

---

## 4. Invariant risks & watch items (owner-tagged)

- **[A] · reduced-motion floor — RESOLVED by A.** `main` shipped **no** global
  `@media (prefers-reduced-motion: reduce)` floor and renders un-gated infinite animations (e.g.
  `SlaTimer`'s `animate-pulse-urgent`), so invariant #7 was only partially met on `main`. A's uplift
  **adds the global floor** (`src/index.css`, "Global reduced-motion contract") **and** the
  `useReducedMotionSafe()` gate (`src/ui/motion.tsx`). C's `reduced-motion.invariant.test.tsx` now
  protects it. ✅ No patch required — do not remove the floor.
  - **Ready-to-enable when A's floor reaches `main`:** the strict e2e assertion "no perpetual animation
    runs under reduced motion" is intentionally **not** committed yet (it would red the gate on `main`,
    which has no floor). Enable it in `e2e/a11y.e2e.ts` once the floor is on `main`:
    ```ts
    const perpetual = await page.evaluate(() => {
      const bad: string[] = []
      for (const el of Array.from(document.querySelectorAll('*'))) {
        const s = getComputedStyle(el)
        if (s.animationIterationCount.split(',').some((c) => c.trim() === 'infinite')) {
          const ms = Math.max(0, ...s.animationDuration.split(',').map((d) =>
            d.trim().endsWith('ms') ? parseFloat(d) : parseFloat(d) * 1000))
          if (ms > 50) bad.push(`${el.className || el.tagName}`)
        }
      }
      return bad
    })
    expect(perpetual).toEqual([])
    ```
- **[C] · axe-core a11y sweep — next increment.** Automated contrast/ARIA audits need the
  `@axe-core/playwright` dev-dep. `package.json` is actively churned by A (Motion/Fraunces), so C is
  **not** adding a dep mid-flight to avoid a lock collision. Wiring is ready to land once deps settle:
  `test('axe', async ({ page }) => { const r = await new AxeBuilder({ page }).analyze(); expect(r.violations).toEqual([]) })`.
  Light-theme contrast is the #1 a11y risk of the uplift — A's `/ui-gallery` prints computed AA contrast
  per token; this e2e is the runtime backstop.

---

## 5. Known local-environment caveat

- **Windows CRLF vs Prettier.** `core.autocrlf=true` + no `.gitattributes` made `prettier --check .`
  report all ~151 files locally (working tree CRLF; repo + CI are LF). This is **not** a real gate
  failure — CI (Linux/LF) is green. C added `frontend/.gitattributes` (LF policy); after it lands, a
  one-time `git add --renormalize .` clears the local working tree. `verify.mjs` downgrades this specific
  case to a ⚠ warning so the local floor check stays meaningful.

---

## 6. Coordination note (shared working tree)

The three agents share one working directory, so A's/B's **uncommitted** work (modified `index.css`,
`tailwind.config.ts`, `main.tsx`, `package.json`, new `src/ui/**`, `docs/ui/UI_UPLIFT.md`, …) is visible
on C's branch. To keep merges clean, **C's commit contains only C-owned NEW files** (the harness,
guards, CI, this doc, the working log). C's appends to the shared append-only docs (`CONTEXT.md`,
`docs/ui/OWNERSHIP.md`) are made in the working tree for the orchestrator to land at integration — they
are **not** pulled into C's commit (that would drag in A's uncommitted hunks and cause merge conflicts).
