# Laptop UI-A — UI FOUNDATION — Working Log

> Design-system owner for the "Daylight Forensics" UI uplift. Branch `hawk-eye/ui-foundation`. Owns
> `frontend/src/ui/**`, theme/tokens/global styles, Tailwind config, app-shell chrome, motion, and the
> design contract. Full brief: `HAWK-EYE_UI_UPLIFT_PROMPTS.md` (Prompt A). Contract:
> [docs/ui/UI_UPLIFT.md](../ui/UI_UPLIFT.md) · ownership: [docs/ui/OWNERSHIP.md](../ui/OWNERSHIP.md).

## Status (2026-07-01)

**v0.1 foundation COMPLETE & gates green.** Light-only "Daylight Forensics" theme is the default; the
signature primitive kit ships under `@/ui`; the motion foundation is reduced-motion-aware; a mock-only
`/ui-gallery` renders every token (with live WCAG contrast) and every primitive.

- **typecheck** (`tsc --noEmit`) → clean
- **vitest** → **198 passed / 15 files** (baseline was 149; +23 new kit tests in `src/ui/ui-kit.test.tsx`, floor ≥149 held)
- **build** (`tsc && vite build`) → clean; `/ui-gallery` is its own 22.6 kB lazy chunk
- **eslint** → my files clean (the only errors are in an untracked `frontend/scripts/check-test-count.mjs` left from a prior session — not on main, not mine, not committed)
- **prettier** → all my `.ts/.tsx/.css/.md/.html` files pass `--check`

## Decisions

- **House style = "Daylight Forensics"** — a bright editorial ops-room (forensic case-file × financial
  terminal, in daylight). Rejected the dark terminal default and a second SaaS-purple accent.
- **One accent = deep ink-teal** (`--primary: 184 62% 26%`). Institutional, not trendy.
- **Sacred risk ramp is colorblind-safe** (hue **and** value shift): low sage/slate → medium amber →
  high ember → critical vermilion. Tuned for WCAG AA on porcelain; verified live in the gallery.
- **Canvas = layered warm off-whites** (porcelain bg / bone card / paper muted), warm near-black ink;
  **hairlines over shadows** (one `shadow-dossier` max); textures (`bg-paper-grain`, `bg-blueprint`)
  are **opt-in** and banned behind dense data.
- **Deep-ink sidebar rail** kept against the light canvas — an editorial signature, not "dark mode".
- **Three type voices:** Fraunces (display serif) / Inter (body) / JetBrains Mono (**all** evidence —
  IDs, hashes, timestamps, ₹). Self-hosted variable faces (no layout shift, on-prem safe).
- **Motion = Motion v12 (`m.*` + LazyMotion) + AutoAnimate**, one vocabulary, all gated by
  `useReducedMotionSafe()`. That hook reads `matchMedia` directly via `useSyncExternalStore` (not
  Motion's cached hook) so it stays live and is deterministic in tests.
- **Testability contract:** every animated primitive always carries its **final** value in the DOM
  (text or `aria-label`) — a reduced-motion user and the test runner both see the real number. Number
  roll-ups accept `durationMs={0}` as an instant escape hatch.
- **Left B & C's turf alone.** No feature screen (`src/views/**`) or CI harness touched. Existing
  shadcn primitives (`components/ui/**`) are re-themed for free by the token flip; `ScoreGauge` stays
  for compact inline use, `RiskGauge` is the richer signature dial.

## Files

- **Contract/coordination:** `docs/ui/UI_UPLIFT.md` (tokens + motion + primitive API + changelog),
  `docs/ui/OWNERSHIP.md` (A/B/C split), `CONTEXT.md` (integration-log entry), this log.
- **Theme:** rewrote `frontend/src/index.css` `:root` to the light palette (+ textures, `shadow-dossier`,
  shimmer, global reduced-motion guard); `.dark` kept as a fallback only. `frontend/index.html` — dropped
  `class="dark"`, `color-scheme: light`. `frontend/tailwind.config.ts` — added `font-display` (Fraunces).
  `frontend/src/main.tsx` — load Fraunces variable font.
- **Motion:** `frontend/src/ui/motion.tsx` (`MotionProvider`, `RouteTransition`, `useReducedMotionSafe`,
  `useAutoAnimateList`, `useMagnetic`, variants); mounted `MotionProvider` in `src/app/Providers.tsx`.
- **Primitives:** `frontend/src/ui/{RiskGauge,AmountFlip,SlaRing,Sparkline,PeerStrip,HashChainBlock,EventTicker,PaperField}.tsx`,
  barrel `frontend/src/ui/index.ts`.
- **Gallery:** `frontend/src/ui/gallery/{UiGallery.tsx,contrast.ts}`; one lazy route `/ui-gallery` added to `src/app/router.tsx`.
- **Tests:** `frontend/src/ui/ui-kit.test.tsx` (23 tests: every primitive + the contrast helper + the reduced-motion contract).
- **Deps:** `motion@^12`, `@formkit/auto-animate@^0.9`, `@fontsource-variable/fraunces@^5`.

## Invariants preserved

Alert-only (no primitive offers block/classify), contestability, watch-the-watchers (`HashChainBlock`,
`EventTicker`), audited unmask untouched, RBAC/SoD gating untouched, MSW mock-mode intact, **no invented
API fields** (primitives take plain props; no new backend shapes), a11y + `prefers-reduced-motion`
honoured, all gates green.

## Handoffs

- **B (features):** consume the kit from `@/ui`; if a primitive is missing, request it in
  `UI_UPLIFT.md` (tag `[A]`) and stub locally behind the agreed API until it lands. Use
  `riskColor()`/`severityForScore()`/`slaInfo()` — never hand-pick a risk colour.
- **C (integrity):** the reduced-motion invariant note in `src/__invariants__/reduced-motion.invariant.test.tsx`
  can now assert `useReducedMotionSafe()` from `@/ui`; the gallery's contrast column is a ready hook for
  an axe/contrast sweep. Remove/relocate the stray untracked `frontend/scripts/check-test-count.mjs` (harness).
