# Laptop log — UI-B (feature screens) · branch `hawk-eye/ui-features`

Agent B for the **Daylight Forensics** UI uplift. I re-skin the 12 investigator screens by composing
Agent A's kit (`@/ui`). I do **not** touch theme/tokens/Tailwind/shell/harness (A + C lanes).
Contract I build against: `docs/ui/UI_UPLIFT.md`. Ownership: `docs/ui/OWNERSHIP.md`.

## Coordination reality (important)
All three agents (A/B/C) share **one working tree**; work is uncommitted on top of `67c143e`.
Rules I follow to stay collision-free:
- Edit **only B-owned files**: `src/views/**`, domain composites in `src/components/**` (NOT
  `components/ui/**`, `components/layout/**`, `components/command/**`), their tests, this log.
- **Do not edit `MaskedPII.tsx`** — A owns its peel/decrypt visual (UI_UPLIFT §4). Compose it as-is.
- `git add` **explicit paths only**, never `-A`. Never `git checkout`/switch branches (would yank the
  shared tree out from under A/C).
- Full `vite build` / `tsc` green is a *shared* signal (C's gate). For my own checks I read tsc output
  and attribute errors to owner (mine vs `src/ui/**` = A, `src/__invariants__/**` = C).

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

## Progress
- [x] Kickoff: CONTEXT append, this log/crib, ownership read, deps confirmed (motion, auto-animate, fraunces).
- [ ] Global: `PageHeader` → `font-display` editorial heading (re-skins all screens).
- [ ] Exemplars: TriageQueue, AlertDetail/AlertHeader.
- [ ] Heart: ExplanationPanel (SHAP waterfall), Auditor (HashChainBlock), Peer (PeerStrip).
- [ ] Breadth: remaining screens.
- [ ] e2e invariants + gates green + screenshots.
