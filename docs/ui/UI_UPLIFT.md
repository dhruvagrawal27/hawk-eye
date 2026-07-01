# UI_UPLIFT.md — Daylight Forensics design-system contract

> Owned by **Agent A** (`hawk-eye/ui-foundation`). This is to the UI what `BACKEND.md` is to the API:
> the single source of truth for tokens, motion, and the primitive API. **B and C read it; only A edits
> it.** Propose changes by tagging `[A]` in `CONTEXT.md`. Every invariant in `HAWK-EYE_UI_UPLIFT_PROMPTS.md`
> (alert-only, contestability, watch-the-watchers, RBAC/SoD, no client secrets, no invented API fields,
> a11y + `prefers-reduced-motion`, green gates) is preserved by this system.

## 0. House style — "Daylight Forensics"

A bright, editorial **operations room**: a forensic case-file crossed with a financial terminal, in
daylight. **Light‑only** (the old `.dark` terminal theme is retired as the default). Layered warm
off‑whites (porcelain/bone/paper), warm near‑black ink, **one** institutional accent (**deep
ink‑teal** — deliberately _not_ SaaS purple), a sacred colorblind‑safe risk ramp, hairline rules over
shadows, an 8pt grid, and **monospace for all forensic data** (IDs, hashes, timestamps, ₹ amounts).

## 1. Design tokens

All tokens are CSS variables in `frontend/src/index.css` (`:root`) surfaced through
`frontend/tailwind.config.ts`. Consume the **Tailwind classes** (`bg-background`, `text-foreground`,
`text-severity-high`, …) or the raw vars (`hsl(var(--accent))`) — never hardcode hex.

### 1.1 Canvas planes (warm off‑whites — never pure `#fff` everywhere)

| Token                      | var                       | HSL           | Use                     |
| -------------------------- | ------------------------- | ------------- | ----------------------- |
| porcelain (base)           | `--background`            | `40 30% 97%`  | app canvas              |
| bone (card)                | `--card` / `--popover`    | `42 42% 99%`  | dossiers, popovers      |
| paper (raised/muted)       | `--muted` / `--secondary` | `40 18% 94%`  | rails, chips, wells     |
| teal-wash (hover/selected) | `--accent`                | `184 34% 91%` | hover/selected surfaces |

### 1.2 Ink (warm near‑black — never `#000`)

| Token     | var                                | HSL          |
| --------- | ---------------------------------- | ------------ |
| ink       | `--foreground`/`--card-foreground` | `30 14% 12%` |
| ink‑muted | `--muted-foreground`               | `30 8% 40%`  |

### 1.3 Accent — the single brand colour

**Deep ink‑teal** — `--primary: 184 62% 26%` (fg bone). Forensic/institutional. The **only** brand
accent; do not introduce a second. `--ring` mirrors it (`184 62% 30%`).

### 1.4 Risk ramp (sacred — never decorative; colorblind‑safe: hue **and** value shift)

| Band      | var                               | HSL                         | Reads as          |
| --------- | --------------------------------- | --------------------------- | ----------------- |
| low       | `--severity-low`                  | `156 30% 32%`               | sage/slate — calm |
| medium    | `--severity-medium`               | `35 90% 39%`                | amber — caution   |
| high      | `--severity-high`                 | `18 82% 45%`                | ember — urgent    |
| critical  | `--severity-critical`             | `2 72% 44%`                 | vermilion — alarm |
| info/flat | `--severity-info` / `--risk-flat` | `199 72% 37%` / `30 6% 45%` | neutral           |

Aliased to `risk.{low,medium,high,critical,flat}` and `severity.*` in Tailwind. Use `riskColor()` /
`riskLevel()` / `severityForScore()` (from `@/ui`) — never pick a risk colour by hand.

### 1.5 SLA bands, reason‑code provenance, AI/TEE

`--sla-{ok,warn,urgent,breached}` (green→amber→ember→vermilion); `--reason-{rule,shap,graph}`
(rule = teal‑info, shap = plum, graph = green); `--ai` (plum) + `--tee` (green). Keep the
reason‑code source colours stable — the explanation panel relies on them.

### 1.6 Borders / radii / elevation / spacing / z

Hairline border `--border: 36 18% 87%`; `--radius: 0.55rem` (lg; md −2px; sm −4px). **Hairlines over
shadows** — one soft dossier shadow (`shadow-dossier`) max; no drop‑shadow soup. 8pt spacing grid
(Tailwind default 4px step → use even steps). Z layers: base 0 · sticky 10 · dropdown 40 · overlay 50
· toast 60 · command palette 70.

### 1.7 Typography

| Role                           | family                                      | rule                                      |
| ------------------------------ | ------------------------------------------- | ----------------------------------------- |
| display (headings/eyebrows)    | **Fraunces Variable** (high‑contrast serif) | editorial; `font-display`                 |
| body                           | **Inter Variable**                          | `font-sans`                               |
| **evidence** (IDs/hashes/ts/₹) | **JetBrains Mono Variable**                 | `font-mono`, **always** for forensic data |

Tabular + slashed‑zero numerals everywhere data lives (`tabular-nums slashed-zero`, already on
`table`/`.tabular`/`.font-mono`). Self‑hosted via `@fontsource-variable/*` (no layout shift).

### 1.8 Textures (opt‑in only — never behind dense data)

`.bg-paper-grain` (micro‑noise) and `.bg-blueprint` (hairline graph‑paper grid) utilities for empty
regions / hero rails. Both are **off** by default and must not sit under tables/charts.

## 2. Motion vocabulary

Standardized on **Motion** (`motion`, import `motion/react`, v12) + **AutoAnimate** for lists.
Everything is **`prefers-reduced-motion`‑aware**: with reduced motion, transforms/springs degrade to
**instant or opacity‑only**. Import from `@/ui/motion`.

| Name                        | export                               | duration/easing              | reduced‑motion degrades to         |
| --------------------------- | ------------------------------------ | ---------------------------- | ---------------------------------- |
| page/route transition       | `RouteTransition`, `pageVariants`    | 220ms ease‑out, y 6→0 + fade | fade only (120ms)                  |
| staggered list reveal       | `staggerParent`, `staggerItem`       | 40ms stagger, 180ms          | all appear at once                 |
| shared element queue→detail | `layoutId` convention (`alert-<id>`) | Motion `layout` spring       | instant (no layout anim)           |
| number roll‑up              | `AmountFlip`/`CountUp` (built‑in)    | 700ms ease‑out               | final value instantly              |
| list add/remove/reorder     | `useAutoAnimateList()`               | AutoAnimate default          | disabled                           |
| focus spotlight             | `spotlight` variant                  | 160ms                        | opacity only                       |
| magnetic CTA                | `useMagnetic()` (Button `magnetic`)  | spring 150/12                | no transform                       |
| skeleton shimmer            | `.animate-shimmer` / `Skeleton`      | 1.4s linear                  | static muted block                 |
| toast                       | sonner (themed)                      | default                      | reduced motion respected by sonner |

Contract: **`useReducedMotionSafe()`** is the single gate; every primitive here calls it. Motion stays
**off the hot path of data‑heavy screens** (triage rows use AutoAnimate, not per‑row springs).

## 3. Component API index (primitives A ships; B composes)

Owned dir: **`frontend/src/ui/`** (new). Existing shadcn primitives in `src/components/ui/` remain
valid and are re‑themed by the token flip; A adds the **signature** layer below. Import from `@/ui`.

| Component         | signature                                                                                                 | purpose                                                                                       |
| ----------------- | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `RiskGauge`       | `{ score:number, max?:number, confidence?:number, size?:'sm'\|'md'\|'lg', flip?:boolean, label?:string }` | animated 0–N arc meter, risk‑ramp colour, confidence hatch ring, optional split‑flap headline |
| `AmountFlip`      | `{ value:number, kind?:'inr'\|'plain', className?:string }`                                               | roll‑up numeral; INR lakh/crore grouping; tabular; reduced‑motion → instant                   |
| `CountUp`         | `{ value:number, decimals?:number, durationMs?:number }`                                                  | generic animated integer/float roll‑up                                                        |
| `SlaRing`         | `{ dueTs:string, now?:Date, size?:number }`                                                               | RBI ≤30‑day TAT countdown ring, SLA‑band colour                                               |
| `Sparkline`       | `{ points:number[], stroke?:string, width?, height? }`                                                    | inline trend line (SVG, no dep)                                                               |
| `PeerStrip`       | `{ value:number, peerMean:number, peerP95:number, min?, max?, label? }`                                   | peer‑relative deviation marker (scoring is peer‑relative)                                     |
| `HashChainBlock`  | `{ index:number, hash:string, prevHash?:string, ok?:boolean, ts?:string }`                                | one WORM/tamper‑evident chain block (auditor screen assembles a chain)                        |
| `EventTicker`     | `{ items:TickerItem[], live?:boolean }`                                                                   | calm split‑flap tape of the synthetic event stream; low‑key; off by default on dense screens  |
| `RouteTransition` | `{ children }`                                                                                            | reduced‑motion‑aware route wrapper                                                            |
| `PaperField`      | `{ as?, grain?, grid?, children }`                                                                        | opt‑in textured empty‑region surface                                                          |

Helpers (all from `@/ui`): `useReducedMotionSafe()`, `useAutoAnimateList()`, `useMagnetic()`,
`severityForScore(score)`, `riskColor(input)` / `riskLevel(input)`, `slaInfo(dueTs)`,
`formatINR(value)` / `formatINRCompact(value)` (re‑exported from `@/lib/*`).

**Gallery:** `/ui-gallery` (mock‑only route) renders every token pair (with computed AA contrast) and
every primitive so B and C can see the kit in one place.

## 4. Invariant hooks the kit exposes (so B keeps them literally)

- `MaskedPII` (existing, in `components/`) stays the audited unmask; A ships the **peel/decrypt**
  visual + the "this view was logged" toast contract — behaviour (audit call) unchanged.
- No primitive offers an auto‑block/auto‑classify affordance. `RiskGauge`/`SeverityPill` render score
  only; the money path stays human `block-request` → lead `approve` in feature screens (B).
- Every colour meets **WCAG AA** on porcelain — verified in the gallery (contrast column) and by C's axe/contrast audit.

## 5. Changelog

- **2026‑07‑01 — v0.1 (A):** Initial Daylight Forensics token set (light‑only), motion foundation
  (Motion v12 + AutoAnimate, reduced‑motion gate), signature primitives (`RiskGauge`, `AmountFlip`,
  `CountUp`, `SlaRing`, `Sparkline`, `PeerStrip`, `HashChainBlock`, `EventTicker`), `/ui-gallery`.
  Fonts: added Fraunces (display). Baselines held: vitest ≥149, e2e ≥3.
