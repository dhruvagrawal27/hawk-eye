# Laptop log — UI-B (feature screens) · branch `hawk-eye/ui-features`

Agent B for the **Daylight Forensics** UI uplift. I re-skin the 12 investigator screens by composing
Agent A's kit (`@/ui`). I do **not** touch theme/tokens/Tailwind/shell/harness (A + C lanes).
Contract I build against: `docs/ui/UI_UPLIFT.md`. Ownership: `docs/ui/OWNERSHIP.md`.

## Coordination reality (important) — RESOLVED via isolated worktree
A/B/C were originally sharing **one working tree + one git HEAD**, which caused live collisions (my
SHAP commit briefly landed on A's `ui-foundation` branch when A checked out the shared tree between my
commits). **Fixed:** I now work in a dedicated **`git worktree`** at `../hawk-eye-uib`
(branch `hawk-eye/ui-features`), so A/C keep the main tree and I'm isolated.
- A's kit is still uncommitted on A's branch, so I **snapshot** A's current foundation into my worktree
  as local files to build/preview against: `src/ui/**`, `src/index.css`, `tailwind.config.ts`,
  `package.json`/lock, `src/__invariants__/**` (C), `docs/ui/**`. `node_modules` is a junction to the
  main checkout. **Reconcile** when A formally lands its foundation (rebase/merge).
- I **commit only B-owned paths** with explicit paths — never the snapshotted A/C files.
Rules I still follow:
- Edit **only B-owned files**: `src/views/**`, domain composites in `src/components/**` (NOT
  `components/ui/**`, `components/layout/**`, `components/command/**`), their tests, this log.
- **Do not edit `MaskedPII.tsx`** — A owns its peel/decrypt visual (UI_UPLIFT §4). Compose it as-is.
- Gates run in my worktree. Baseline in worktree: **tsc 0, vitest 198**.

## House-style crib — apply consistently to every screen
Import surface: `import { RiskGauge, AmountFlip, CountUp, SlaRing, Sparkline, PeerStrip, HashChainBlock,
EventTicker, PaperField, RouteTransition, useReducedMotionSafe, useAutoAnimateList, useMagnetic,
staggerParent, staggerItem, m, AnimatePresence, severityForScore, formatINR, formatINRCompact, slaInfo,
riskColor, riskLevel } from '@/ui'`.

1. **Route wrapper.** Wrap the view's returned root in `<RouteTransition>` (reduced-motion-safe fade).
   Keep the existing outer layout classes on the `RouteTransition` via `className` where it had them.
2. **Headings.** Titles use the editorial serif: add `font-display` (via `PageHeader`, already done —
   every screen inherits it). Section labels: `Eyebrow` (mono-uppercase) from `@/components/ui/eyebrow`.
3. **Evidence is mono.** Every ID / hash / timestamp / ₹ amount renders in `font-mono` with
   `tabular-nums`. Never a hardcoded hex colour — use tokens (`text-severity-high`, `text-muted-foreground`).
4. **Signature numbers.**
   - Headline risk → `RiskGauge` (`{ score, confidence, size, flip }`; `flip` = split-flap headline).
   - ₹ exposure / money → `AmountFlip value={n} kind="inr"` (lakh/crore, reduced-motion → instant).
   - Generic counts that animate → `CountUp value={n}`.
   - SLA/TAT → `SlaRing dueTs={iso}` (keep `SlaTimer` text where a compact inline label is better).
   - Peer-relative → `PeerStrip { value, peerMean, peerP95 }` (scoring is peer-relative, never a bare threshold).
   - Inline trend → `Sparkline points={[...]}`.
5. **Motion, off the hot path.** Live/adding lists get `const [ref] = useAutoAnimateList()` on the
   container. Load reveals use `staggerParent`/`staggerItem` on a `m.div`. **No per-row springs** on
   dense tables (triage). Everything degrades under `useReducedMotionSafe()`.
6. **Invariants must be visible (these are the product):**
   - **Contestability:** always render reason codes; if an alert/explanation has none, show an explicit
     `"No reason codes — alert invalid"` state (amber/severity), never a blank.
   - **Alert-only:** the only money path is a human **block-request** → lead **approve**. Never render
     an auto-block/auto-classify affordance. Keep the "nothing auto-blocks" copy visible on detail.
   - **Audited unmask:** use `MaskedPII` (fires audit + "logged" toast). Don't reimplement it.
   - **RBAC/SoD:** keep every `can(...)` / role gate exactly; a redesign never widens access.
7. **States with character.** Loading = `Skeleton`/`.animate-shimmer` mirroring the real layout; empty =
   `EmptyState` with an apt icon + one-line guidance; error = `QueryBoundary` retry. No bare spinners on
   primary content.
8. **Surfaces.** Dossier feel: `Card`/`Surface` with hairline borders + at most one `shadow-dossier`;
   `PaperField grain`/`grid` only in genuinely empty hero regions, never under tables/charts.

## Progress — COMPLETE
- [x] Kickoff: CONTEXT append, this log/crib, ownership read, deps confirmed (motion, auto-animate, fraunces).
- [x] Global: `PageHeader` → `font-display` editorial heading (re-skins all screens).
- [x] Exemplars: TriageQueue, AlertDetail, AlertHeader (RiskGauge + confidence ring, AmountFlip ₹, SlaRing, reason-code strip + invalid state).
- [x] Heart: ExplanationPanel (animated cumulative SHAP **waterfall**), Auditor (HashChainBlock WORM chain + PASS/FAIL seal), Peer (PeerStrip on every dimension), Entity-360 (evidence tape + gap markers).
- [x] Breadth: all remaining screens (Cases, EDD, Compliance four-eyes, Model-eng, Admin, Reporting/KRI, Org, Replay/EventTicker, Dashboard). 4 parallel sub-agents, disjoint files.
- [x] Gates (isolated worktree): **tsc 0 · eslint 0 · prettier clean · vitest 200 · vite build ok**.
- [x] e2e: **5/5 Playwright pass** against the worktree app (login → triage → detail → explanation → disposition; RBAC; alert-only; onboarding non-blocking).
- [x] Visual: dev server (:5178) + Playwright screenshots of login/dashboard/triage/alert-detail/SHAP-waterfall/auditor — Daylight Forensics renders (porcelain canvas, ink-teal accent, risk ramp, Fraunces headings, mono evidence).

Commits on `hawk-eye/ui-features`: `51bf205` (kickoff + hero) · `5450a41` (SHAP waterfall) · `a351e4c` (all remaining screens).

## Reconcile with A (for whoever integrates)
- `hawk-eye/ui-features` contains **only B-owned files** (views + domain composites + tests + this log +
  the CONTEXT append). It was built against a **local snapshot** of A's `@/ui` kit + theme (see the
  worktree note above); those A/C files are NOT committed here.
- **Integration order (per the orchestration cheat-sheet): land A's `ui-foundation` first**, then merge
  `ui-features` — B's `@/ui` imports resolve against A's real primitives. Ownership is disjoint, so the
  merge is clean.
- **Cleanup flag for A:** during the early shared-tree phase my commit `96e476c` (ShapChart +
  ExplanationPanel) briefly landed on `ui-foundation`. Its content is already on `ui-features` (as
  `5450a41`), so **`96e476c` can be dropped from `ui-foundation`**.
- Verification-only local edits in the worktree (NOT committed): `vite.config.ts` `server.fs.allow`
  (to serve fonts through the node_modules junction), `__shot.mjs`, `__e2e.config.ts`.
