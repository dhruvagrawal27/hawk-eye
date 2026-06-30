# Hawk-Eye — Design & Feature Upgrade Study

> **What this is.** A thorough study of the `hawkeye-idea` prototype, our current `frontend/`, and 2025–2026 best practices for advanced fraud-investigation consoles — distilled into a prioritized plan to make our app feel **super advanced** (a Bloomberg-grade operations terminal, not a SaaS dashboard). Produced by a 5-agent study (mine-the-prototype × inventory-ours × research-the-field).

---

## 0. The thesis in one paragraph

We already built the **correct, rigorous** app — RBAC done exactly, virtualized tables, contract tests, alert-only enforcement, a real explanation panel, a Cytoscape graph. What we **lack** is *soul*: the prototype (`hawkeye-idea`), despite "bad CSS and not-quite-right logic," nails the **operations-terminal feel** — a live status tape, a streaming Bloomberg-style event ticker, score gauges, an incremental Neo4j-style graph, mono tabular numerics, color-coded severity everywhere. **The move is to keep our correctness and graft the prototype's terminal soul on top**, rebuilt cleanly in our stack (React 19 + Radix + CVA + Tailwind + Recharts + Cytoscape). The two cheapest changes (load the fonts + tabular-nums, and the radial-gradient terminal background + tokenized severity) move the needle the most; the three "wow" builds (live status bar, live event tape, expandable graph + linked timeline) win demos.

**The gap, one line:** *We have a dashboard that is correct; the prototype has a terminal that feels alive. Fuse them.*

---

## 1. What to STEAL from the prototype (high impact, mostly cheap)

These are *ideas worth taking* — rebuilt in our stack, not copied (their CSS is `@apply` soup, their logic churns effects). Ranked by leverage.

| # | Element (prototype) | Why it matters | Build in our stack | Impact | Effort |
|---|---|---|---|---|---|
| S1 | **Typography system**: JetBrains Mono + `tabular-nums` + `slashed-zero`, mono-uppercase eyebrows, 9/10px micro-sizes | *The single biggest "dashboard→terminal" lever.* Our Inter/JetBrains are **declared but never loaded** — we silently render in system fonts. | `@fontsource` Inter + JetBrains Mono; enable `font-variant-numeric: tabular-nums slashed-zero` on data containers; add `<Eyebrow>` + `<Stat>` CVA primitives; 2xs/3xs in the type scale | **wow** | S |
| S2 | **Layered radial-gradient terminal background + custom scrollbars** | The two cheapest "tells" that an app is *a terminal*, not *a dark theme*. We use a flat bg + default scrollbars. | Near-black blue body bg (#070A18) with two low-opacity radial glows; thin tokenized webkit + firefox scrollbars | **wow** | S |
| S3 | **Centralized 5-step severity scale** (low/med/high/critical/flat) applied to **badges, numbers, dots, bars, node fills, row flashes** | One color system *everywhere* = coherent + operator-legible. Ours is timid — the rich palette is trapped in tiny badges. | `risk.{low..critical}` as the single Tailwind token source; `<RiskBadge level size>` CVA (critical → `animate-pulse`, gated by `prefers-reduced-motion`); `useRiskColor()` hook so charts + Cytoscape + inline all read one source | **high** | S |
| S4 | **Persistent L0 TopStatusBar** (Bloomberg tape header): live IST clock, per-service health dots, inline KPI strip (ALERTS-24H / HIGH-RISK / EVENTS / EPS), WS live/idle indicator | The most load-bearing element for the terminal feel — makes it read as an *ops terminal*. Our Topbar is thin. | `<StatusBar>` h-7 mono-uppercase strip; **isolate the clock into a memoized `<LiveClock>` leaf** (only it re-renders/sec); health dots = CVA badge (ok/warn/down) with glow token; EPS off a real ring-buffer rate | **wow** | M |
| S5 | **LiveEventTicker / EventTape** — streaming Bloomberg activity tape: per-row risk dot, ▲▼ direction, user/system/access, ₹ amount, risk-colored score, signal glyphs, **freshness flash on new rows**, pause/resume | *Our single biggest demo-feel gap* — nothing in our app conveys live ingestion. This is the heart of the aesthetic. | `<EventTape>` with **one shared `COLUMNS` const** driving header+rows; **lucide icons not emoji**; flash via a CSS keyframe keyed on tick id (no per-row timers); reuse our `@tanstack/react-virtual`; `MaskedPII` on the user column | **wow** | L |
| S6 | **Dense sortable/filterable/bulk-select alert table** | Power-user triage: sortable headers, segmented multi-filter, role-gated bulk actions, skeleton rows. Ours has none of these. | `@tanstack/react-table` (headless) + our mono table CVA; Radix ToggleGroup segmented control; bulk-action bar gated by `useCan()` | **high** | L |
| S7 | **Graph: expand/collapse neighborhood** (Bloom-style incremental) | Avoids the "hairball"; turns the static subgraph into a real investigation surface. We inspect-on-click but can't expand. | Cytoscape double-tap → `GET /entities/{id}/graph/neighbors?hops=1` → `cy.add()` + incremental `cose` layout scoped to new nodes; track expanded ids; `+N` collapse badge | **wow** | L |
| S8 | **Graph: search + highlight + center-on-node** | Instant orientation in a big graph. We have no search field. | Input above the canvas → `cy.animate({center, zoom})` + flash class; matches from `graph.nodes` by id/label | **high** | S |
| S9 | **Graph: path-finding / pivot between two entities** | The investigator verb "how are A and B connected?". | Select A→B → `cy.elements().aStar()/dijkstra()` client-side (Cytoscape ships the algorithms — no d3) → highlight path, dim rest (reuse our `.dimmed/.evidence` overlay) | **high** | M |
| S10 | **Alert heatmap (7-day × 24-hour grid)** | Surfaces off-hours bias at a glance — genuinely missing for both Entity-360 and KRI/management screens. | Small pure-SVG grid (matches our existing SVG patterns), IST-bucketed via our format helpers; cell-click → time filter | **high** | M |
| S11 | **Timeline scrub / brush → drives graph + tape** (Bloom-style time travel) | *The differentiator* — turns independent panels into one **linked investigation** surface. | Shared time-window state on the entity/alert shell; Recharts `<Brush>` under a score trend / heatmap → re-query graph + timeline for the slice; highlight in-window nodes | **wow** | L |

---

## 2. What to ADAPT (good idea, needs reshaping for our app)

| Element | Adapt how | Impact | Effort |
|---|---|---|---|
| **Three-tier surface system** (operational / reference / actionable) | `<Surface tone>` CVA with inset-highlight + colored-shadow **tokens** (not `@apply`); drop backdrop-blur on dense lists | high | S |
| **ScoreGauge** (SVG arc + centered tabular number) | Bespoke `<ScoreGauge>` (don't pull Recharts), arc color from risk tokens; **slide-over/detail only**, bare number in lists; 4px micro-arc variant for compact | medium | S |
| **AlertSlideOver investigation workspace** | Rebuild on **Radix Dialog/Sheet** (focus-trap + a11y free); sticky triage footer; keep gauge→composition→SHAP→memo→actions narrative order | high | M |
| **ScoreComposition** ("rescued by graph fusion") | `<ScoreComposition>` driven by API weights (never hardcoded); per-model mini-bars + `<InsightCallout>` counterfactual when one source is decisive | high | M |
| **Score-over-time area chart** | Recharts AreaChart on Entity-360/AlertDetail; 0–100 domain + severity `ReferenceArea` bands; `step` not `monotone` (honest discrete scores) | medium | M |
| **Risk-sized nodes + risk-ring on elevated nodes** | Cytoscape stylesheet `node[risk>=t]` glow via `underlay-color`/border (we already size by risk); threshold from our `severityForScore` | medium | S |
| **Cluster-by-attribute layout** (dept centroids + labeled hulls) | Cytoscape cose + centroid seeding; convex-hull SVG overlay (the one justified thin d3 assist) **or** compound parent nodes | high | M |
| **Live event-rate sparkline** | Port the Recharts rolling-window chart once a WS feed exists; throttle setState ~4–10 Hz via ref+rAF | medium | M |
| **TEEAttestationBadge → `<ProvenanceBadge>`** | Radix Collapsible trust panel (verified=emerald/standard=dim) + mono `<KeyValueGrid>`; lazy-fetch proof on expand | medium | S |
| **Themed Markdown for LLM memos** | `react-markdown` + `remark-gfm` with a components map routing h2/h3→`<Eyebrow>`, code→CVA chip — so AI output is visually native | medium | S |
| **Sidebar mono short-codes + footer model-stats** | Fixed-width mono codes per nav item, active = left-accent border; pin a mono provenance block in the footer; collapsible rail + Radix Tooltip | medium | S |
| **RoleSwitcher (demo capability context)** | Radix DropdownMenu + `useCan()` capability layer; **non-prod builds only**; keep "demo override; prod uses JWT" disclosure | medium | S |
| **OnboardingOverlay (first-run)** | Radix Dialog + localStorage flag; role-aware tour off our `nav-config`/`ROUTE_ROLES`; single "Load demo scenario" CTA | high | S |
| **Mission/Context callout** | Slim collapsible `<ContextCallout>` per role-view: plain-language "what these signals mean," mapped to our feature taxonomy | medium | S |
| **Replay Studio (scenario theater)** | Demo/admin-gated control hitting a backend seed/replay endpoint to inject a scripted scenario (e.g. "after-hours bulk export by treasury RM") → drives the EventTape; toast "N alerts injected" | high | M |
| **Manager Command Center primitives** | Don't add a whole view — steal 3 primitives into Compliance/Reporting: (1) approval/escalation queue (RBAC-gated inline approve/reject), (2) department rollup table by open-alert volume, (3) the 7×24 temporal heatmap | high | L |
| **Layered dashboard tiers (L0–L3)** | Adopt the tier convention; `<PanelHeader eyebrow action>`; replace our thin dashboard (3 stat-cards + links) with live mini-charts + recent-activity + SLA-breach call-outs | high | M |
| **Self-explaining demo affordances** (philosophy) | Never-empty states + per-view self-framing + one "make-it-live" button — strong for a 60-second evaluator, which our deep app currently fails | high | M |

**SKIP (don't bother / we already do it better):** their zustand Toast store (we have `sonner`), their Skeleton primitives (we have them), the Replay *Studio theater* chrome (a single demo button suffices), the demo role-switcher chip as a permanent fixture.

---

## 3. Our current state (so upgrades are additive)

**We HAVE (19):** Tailwind 3.4 + hand-authored shadcn-style primitives (Radix + CVA + tailwind-merge), well-structured HSL token system, TriageQueue (virtualized), AlertDetail, Entity360Timeline, ExplanationPanel (SHAP + rule provenance + LAXCAT attention + AI narrative), GraphView (Cytoscape, risk-sized nodes, ring detection, dimming overlays), PeerComparison, EDD panel (alert-only enforced), Compliance/Auditor/ModelEngineer/Admin/Reporting views, KriDashboard, MaskedPII, RBAC capability gating, contract + e2e tests.

**Design system today:** correct tokens, **but** — declared Inter/JetBrains Mono **never load**; visual hierarchy is flat (almost everything `text-xs/sm`); surfaces are border+`shadow-sm` only (no depth/elevation/glow); **severity is under-expressed in rows** (a critical alert looks ~identical to a low one); the rich domain palette is confined to tiny badges; motion is minimal; charts are stock Recharts with no branded theme.

**MISSING vs an advanced terminal (18):** command palette (Cmd-K) · keyboard triage (j/k, hotkeys) · **any real-time/streaming** (no WS/SSE) · saved views / URL-persisted filters · bulk multi-select · global cross-entity search · density/compact toggle · in-UI theme switch · master-detail split-pane · geospatial/branch map · linked timeline↔graph↔SHAP cross-filtering · notifications/inbox center · collaborative annotations/@mentions · **web fonts actually shipped** · empty/loading/offline states polish · printable PDF case dossier · chart interactivity depth (crosshair sync, zoom, drill-down) · high-contrast/reduced-motion.

---

## 4. Field best practices (2025–2026) we should bake in

- **Bloomberg density:** maximize data-ink; **tabular monospace numerics, right-aligned**; a fixed perimeter (command bar top, **status bar bottom**: connection state, last-updated tick, active case id, counts, latency) framing a resizable split-pane (`react-resizable-panels`) + Radix Tabs. → *sources: Bloomberg Terminal UX writeups, ui-density.*
- **Keyboard-first:** ship a **`cmdk` command palette (Cmd-K)** backed by a central command registry that menus *and* the palette read; full keyboard operability (Radix roving tabindex), vim-style `j/k`/`e`/`x`/`/` on tables+graph, a `?` cheat-sheet. → *uxpatterns.dev, mobbin.*
- **Graph investigation:** **never render the whole graph** (hairball) — seed + expand-on-demand, cap fan-out with "show N more"; first-class verbs **Expand / Pivot / Find-Path / Time-Slice**; collaborative — saved subgraph snapshots, node/edge annotations, "create case from selection." → *Cambridge Intelligence, Neo4j Bloom, Linkurious.*
- **Real-time SOC:** workflow = **triage → investigate → respond → report**; three-tier alert rail (critical pinned/bold, moderate collapsible, info muted); **fight alert fatigue by clustering correlated events into one named incident** with a count badge; convey live-ness explicitly (WS not polling, new-row flash, pulsing connection dot, "updated 2s ago"). → *AufaitUX, ArmorPoint SOC.*
- **Data-viz:** anomaly **heatmap/matrix** (time × technique, entity × behavior) with clickable cells; **perceptually-uniform color (OKLCH via `culori`)** — single-hue sequential for magnitude, blue→neutral→orange diverging for "deviation from normal" (avoid red/green). → *colorarchive, meetcyber.*
- **Dark design system:** dark as a **first-class paired scale** (Radix Colors → semantic Tailwind tokens: `--surface-base/raised`, `--border-subtle`, `--text-muted`); **severity = dedicated 12-step token set, never color alone** — always icon + label, WCAG 4.5:1. → *Radix Colors + Tailwind.*
- **Explainability UI:** never a bare score — a **"Why flagged"** panel of SHAP-style contributions with direction/weight using the diverging palette; an **auditable evidence trail** (model version, feature values, score, explanation snapshot, every analyst action with timestamp/user) rendered as a reverse-chron timeline, **exportable to a case report**. → *didit.me, MDPI.*

---

## 5. The prioritized roadmap

### Phase 0 — Foundation polish *(1–2 days, highest leverage, fixes "CSS is not good")*
The cheap changes that flip the whole feel from "dark dashboard" to "terminal":
1. **Ship the fonts** (`@fontsource/inter` + `@fontsource/jetbrains-mono`) — Inter for prose, **JetBrains Mono for every numeric/id/label/timestamp**.
2. **Enable `tabular-nums slashed-zero`** on all data containers; right-align numerics.
3. **Terminal background** (near-black-blue + two radial glows) + **custom thin scrollbars**.
4. **Severity tokens** `risk.{low..critical}` as the single source → `<RiskBadge>` CVA; **apply risk color to row backgrounds/left-accent-bars and score numbers**, not just badges.
5. **`<Surface tone>` CVA** (operational/reference/actionable) with inset-highlight + colored-shadow tokens → instant depth.
6. **`<Eyebrow>` + `<Stat>`** mono-uppercase primitives; add 2xs/3xs to the scale.
7. **Density toggle** (`data-density` root var: compact 24px rows vs comfortable).

### Phase 1 — The "wow" terminal core *(the demo-winners)*
8. **`<StatusBar>`** (live clock + service-health dots + KPI strip + live indicator), isolated `<LiveClock>` leaf.
9. **`<EventTape>`** live streaming ticker (CSS-keyframe flash, lucide glyphs, MaskedPII, virtualized) — fed by a mock replay generator until the backend streams.
10. **Command palette (`cmdk`, Cmd-K)** + a central command registry + `j/k` triage hotkeys + `?` cheat-sheet.
11. **`<ScoreGauge>`** in the slide-over; **bulk-select + sortable** triage table (`@tanstack/react-table`).

### Phase 2 — Graph investigation upgrade *(Neo4j-grade)*
12. **Expand/collapse neighborhood** + **search/center** + **find-path** + **risk-ring** on the Cytoscape canvas (all client-side first; add a `neighbors` endpoint for true incremental).
13. **AlertHeatmap** (7×24) on Entity-360 + KRI.
14. **Timeline scrub** brush → **linked** graph + timeline + tape (the differentiator).
15. **Cluster-by-attribute** hulls (thin d3 assist for convex hulls only).

### Phase 3 — Advanced / explainability / collaboration
16. **ScoreComposition** + **score-over-time** + **`<ProvenanceBadge>`** + themed AI-memo markdown.
17. **Onboarding overlay** + **Replay Studio** demo button + per-view **Context callouts** (self-explaining product).
18. **Manager-oversight primitives** (approval/escalation queue + dept rollup + heatmap) into Compliance/Reporting.
19. **Notifications/inbox center**, **saved views (URL state)**, **printable PDF case dossier**, **OKLCH viz palette**, master-detail **split-pane** (`react-resizable-panels`).

---

## 6. The "wow" shortlist (if you only do six)
1. **Load the fonts + tabular-nums** (Phase 0.1–0.2) — biggest feel-per-effort.
2. **Terminal background + scrollbars + severity-colored rows** (Phase 0.3–0.4).
3. **Live StatusBar** (clock/health/EPS) — the terminal header.
4. **Live EventTape** — the streaming heart; kills our "feels static" gap.
5. **Command palette (Cmd-K)** — table-stakes for "advanced."
6. **Expandable graph + timeline scrub** — the linked Neo4j-style investigation.

---

## 7. What NOT to copy from the prototype
- `@apply`-soup CSS and magic inline shadow/hex values → use **tokens + CVA**.
- **Re-subscribing the WS on every clock tick** and per-row `setTimeout` flash timers (effect churn / 120 live timers) → subscribe once + **CSS keyframes**.
- **Emoji signal glyphs** (📥🔓⚠ render inconsistently) → **lucide icons**.
- Sloppy EPS math (drifts) → **ring-buffer rate** (events in trailing 5s / 5).
- Dual color maps (RISK_COLOR + RISK_BADGE) → **one tokenized source + `useRiskColor()`**.
- Big consumer-dashboard gauges in dense lists → gauge in detail only, **bare number in lists**.

---

## 8. Libraries to add (small, well-chosen)
`@fontsource/inter`, `@fontsource/jetbrains-mono` (fonts) · `cmdk` (command palette) · `@tanstack/react-table` (we already have virtual) · `react-resizable-panels` (split-pane) · `culori` (OKLCH viz scales) · optionally `d3-polygon` (convex hulls only). **We already have:** Radix, CVA, Tailwind, Recharts, Cytoscape, lucide, sonner, react-query, react-virtual, oidc-client-ts — most upgrades are *composition*, not new deps.

---

## 9. Honest framing
None of this changes our **correctness** (RBAC, alert-only, contracts, explainability) — it's a **presentation + interaction** upgrade layered on the same `apiClient` seam. Many "wow" items (live tape, event-rate, status EPS) need a **WebSocket/SSE feed the backend doesn't expose yet** — until then they run on a **mock replay generator** (which also powers the demo Replay Studio), and swap to the real stream with a one-line source change. Phase 0 alone (≈1–2 days) is what most makes people say *"this looks super advanced."*

---

*Study basis: `hawkeye-idea` prototype (32 components, d3+zustand) · our `frontend/` (82 components, Radix+CVA) · 2025–2026 field research (Bloomberg density, Neo4j Bloom / Linkurious graph UX, SOC dashboards, Radix dark systems, OKLCH viz, explainable-AI UI). Recommendations are mapped to our existing stack — keep the rigor, add the soul.*

---
---

# PART 2 — Making it 10× More Useful for a PSB (Union Bank of India)

> **Appended (additive — nothing above changed).** Part 1 makes the app *look* world-class. Part 2 makes it *worth deploying at a public-sector bank* — grounded in current (2024–2026) RBI / NPCI / I4C / FIU mandates and the live Indian fraud landscape. Research-backed: 71 capability findings across RBI-regulatory, PSB-ops, fraud-landscape, capability-gaps, and our-code-status streams (32 rated **must-have**).

## 2.0 The one insight that unlocks 10×

We built **insider-first** (privileged-user / employee fraud — the PNB-style scam, maker-checker collusion, ghost loans). But **~90% of a PSB's 2025–26 fraud pain — and almost every *new* RBI/I4C mandate — is customer & payment-channel fraud**: mule accounts, UPI/AePS scams, digital-arrest, account takeover. **The 10× move is to add a *customer/account-entity axis* alongside the insider axis, reusing the exact same L0→L6 stack.** Our event model, rules engine, UEBA, GBDT, sequence, graph, fusion, dashboard, EWS/CRILC/FMR generators, governance and audit **all transfer** — we re-point them at customer accounts + payment events and add the India-specific integrations. **It's a scope expansion, not a rebuild.**

## 2.1 Must-have to even deploy at a PSB (regulatory — non-negotiable)

| Capability | Driver (2024–2026) | Our status | What to add |
|---|---|---|---|
| **RBI Master Directions on Fraud Risk Management 2024** — full RFA lifecycle | DOS.CO.FMG.SEC.7/2024-25 (15 Jul 2024); SBI v. Rajesh Agarwal (SC 2023) | PARTIAL | RFA **state machine** (flag→RFA-tag→7-day CRILC/RBI report→~180-day classification) with timers; **SCBMF board pack** generator; staff-accountability case workflow (6-month clock) |
| **EWS integrated with CBS** (borrower/credit, not just insiders) | RBI MD 2024 — EWS/RFA chapter | PARTIAL | Standard **~40-signal RBI EWS indicator library** (LC/BG devolvement, fund routing, turnover fall…) wired to L1/L3; a **CBS borrower-trigger adapter** (SCAFFOLD); per-trigger remediation SLA |
| **CRILC + Central Fraud Registry (CFR)** | RBI MD 2024 (3-cr / 7-day / 180-day) | PARTIAL | **CFR screening service** — check beneficiaries/borrowers against CFR *before* disbursement & as an EWS signal (currently MISSING); 7-day RFA→CRILC timer |
| **FMR automated generation + submission** | RBI MD 2024 (FMR returns) | PARTIAL | Populate from the confirmed-fraud **case lifecycle** + recovery fields + quarterly periodization; **balance-sheet reconciliation** hooks; submission channel (SCAFFOLD) |
| **FIU-IND STR/CTR/CCR/CBWTR via FINnet 2.0 (FINGate 2.0)** | PMLA 2002; FINnet 2.0 (STR ≤7 days) | **MISSING** | A whole **AML reporting module** — STR auto-draft (7-day clock), CTR/CCR/CBWTR generators, FINnet-2.0 XML/schema validator + submit. We have **zero** AML reporting today |
| **Automated regulatory submission** (not just generation) | RBI MD 2024; CRILC; CFR/CKYCR | PARTIAL | Submission adapters (RBI fraud portal, CRILC, CFR, CKYCR) with **ack/retry/audit** — generating a report ≠ compliance; timely *submission* is the duty |
| **Mule-account detection + MuleHunter.AI** | RBIH MuleHunter.AI (Dec 2024); **MHA directive: ALL FIs integrate by Dec 2026** (26 banks live Dec 2025) | **MISSING** | Customer-side mule module (below) + MuleHunter.AI consumption adapter |
| **DoT Financial Fraud Risk Indicator (FRI)** | RBI advisory **30 Jun 2025** — all SCBs integrate FRI (prevented ~₹660 cr in 6 mo) | **MISSING** | DoT **DIP/FRI connector** (SCAFFOLD); normalize FRI tier into L0 as a high-weight feature → L6 fusion + EDD reason codes + the decision engine |
| **I4C / NCRP / 1930 / CFCFRMS golden-hour freeze** | MHA/I4C SOP **2 Jan 2026** (liens within hours); 1930 helpline | **MISSING** | CFCFRMS intake connector + **golden-hour freeze queue** (SLA countdown) + one-click **human-confirmed lien/hold** against CBS + reverse status reporting + Money Restoration Module |
| **AePS Touchpoint-Operator (ATO) monitoring** | RBI AePS-ATO Due-Diligence Directions (27 Jun 2025, **in force 1 Jan 2026**) | **MISSING** | Mandated **ongoing ATO transaction monitoring** + location profiling (below) |
| **RBI FREE-AI + Model Risk Mgmt (MRMF) — kill-switch** | RBI FREE-AI report (13 Aug 2025); draft MRMF 2026 | PARTIAL | Model **kill-switch** per model; **7-dimension validation** artifacts (explainability/hallucination/bias/overfit/spurious-corr/output-variability/data-risk); risk-tier metadata in the registry |
| **RBI Authentication Directions 2025 (eff. 1 Apr 2026)** — real-time risk-based monitoring + outlier confirmation | RBI Authentication Mechanisms for Digital Payment Transactions Directions 2025 | **MISSING** | Real-time pre-debit scoring + **outlier pre-confirmation gate** (below) |

## 2.2 The big new detection capabilities (the product expansion)

1. **Mule-account network scoring (customer accounts).** Port the **~19 MuleHunter behaviours** into L1 rules + L2 UEBA + **re-point L5 graph at customer accounts** (today `ml/layers/l5/graph_build.py` makes the *employee* the primary node — tuned for maker-checker rings, not mule chains). Signals: rapid pass-through ratio, fan-in/fan-out degree, dormant→active, many-to-one beneficiary, new-account high-velocity, structuring. *This is the single highest-impact new detector for a PSB.*
2. **Real-time payment-transaction scoring (UPI / IMPS / NEFT / RTGS).** A **customer-payment L0 event** (payer/payee/VPA/device) + a fast-lane scorer reusing L1+L2+L3: new-payee→high-value latency, amount-vs-personal-baseline, velocity/burst, odd-hour, device/SIM-swap+payment correlation, beneficiary-cooling-period breach. (UPI fraud rose ~85% FY24; India ran 228 B UPI txns / ₹300 T in 2025.)
3. **AePS / BC / micro-ATM monitoring (PSB-critical, rural).** Model the **BC operator as a first-class actor — exactly like an employee, so our insider UEBA (L2) + reversal-clustering (L1) transfer directly**: per-terminal velocity, unique-Aadhaar-per-device, geo-mismatch (customer vs outlet), biometric-failure clustering, withdrawal-only patterns; extend L5 to ATO↔customer collusion rings. (RBI logged a **+340% AePS-fraud spike**, >₹1,200 cr.)
4. **Device / endpoint risk telemetry.** Add a device block to the customer L0 event: app-integrity, **screen-share active, remote-access detected, accessibility-abuse, SIM-changed, device-binding-age, root/emulator** → L1 rules + L2 features. (Malicious-APK + screen-share dominate 2025; ATO via malware+SIM-swap +310% YoY.)
5. **Digital-arrest / social-engineering victim detection.** Victim-side behavioral detector: **change-point on the customer's transfer baseline**, FD-break-then-transfer, loan-against-deposit-then-transfer, panic-pattern (rapid drain to new payees). (₹2,140 cr lost to digital-arrest in 18 mo; **Supreme Court Feb 2026 directed banks to build a flag-and-act mechanism**.)

## 2.3 The real-time decision layer — reconciling "alert-only" with RBI's "interdiction" expectation

The tension to resolve cleanly: RBI now expects banks to **decline/hold/step-up suspicious transactions in real time** (FRI advisory; Authentication Directions) — *not* only post-hoc alerts. Yet our **alert-only / natural-justice** stance is *also* RBI-required (SBI v. Rajesh Agarwal — never auto-*classify* a person as a fraudster without a hearing).

**Resolution — add an `L6.5` decision-policy engine** that emits, per *transaction*: `{ ALLOW · STEP_UP (re-auth/2FA) · HOLD_FOR_REVIEW (time-boxed pending queue) · SOFT_DECLINE_WITH_CUSTOMER_CONFIRM }`. This is **transaction friction** — reversible, customer-confirmable, time-boxed — which is *categorically different* from **classifying a person as a fraudster** (still human + show-cause + the existing EDD/RFA lifecycle). This single addition makes us compliant with the new real-time directives **without** violating natural justice, and it's fully defensible to an RBI inspector. *Highest-value architectural addition in Part 2.*

## 2.4 Customer-facing loop

- **Outlier pre-confirmation gate** (RBI FRM "prior confirmation for outlier transactions") wired to the real-time scorer.
- **Two-way fraud alerts** (SMS/app: confirm / pause / "not me") — **vernacular/multilingual** (Hindi + regional), essential for a PSB's rural base.
- **EBT zero-liability dispute workflow** (RBI Limiting Liability): 5-working-day reporting window capture, liability computation (bank-negligence→zero; third-party + timely report→zero), re-credit timers.
- **MNRL hook**: when an account's registered mobile appears on the **Mobile Number Revocation List**, raise enhanced-monitoring / possible-mule.

## 2.5 Consortium / cross-bank intelligence (our single-bank graph can't see the whole mule chain)

Add connectors (SCAFFOLD until creds): **RBI DPIP** negative-registry (mandated API integration + mule reporting), **NPCI federated risk-scoring** (combine our score with NPCI device/txn profiling in real time), **I4C Suspect Registry** (24.67 lakh mule accounts flagged), **CFR**, **MNRL**. Extend L5 to consume **cross-bank edges/labels** so a mule chain visible to the consortium lights up in our graph.

## 2.6 Union-Bank-of-India-specific realities

- **Merged Finacle CBS silos** (Andhra + Corporation merged into Union, 2020): **dedupe CIF across ex-Union/Andhra/Corporation** to compute true CRILC aggregate-exposure, a unified customer master for CFR screening, and a complete mule graph. *We have `data/mdm/entity_resolution.py` for employees — extend it to the customer master.*
- **PMJDY / DBT mule hosting**: PSBs hold the **largest no-frills/Jan-Dhan base** that fraudsters recruit as mules, often opened via **BC/AePS in Tier-2/3 towns** — exactly MuleHunter's target segment.
- **DBT / government-scheme disbursement fraud** (ghost beneficiaries, duplicated Aadhaar, diversion) — a slow-lane typology to add.
- **Vernacular** complaints, narratives, and customer alerts (the TEE-LLM gateway already drafts narratives — add language packs).
- **On-prem / India data-residency**: we already **HAVE** this (OPA/Conftest residency gates, Vault/HSM, retention windows) — the one axis where we're ahead of most vendors.

## 2.7 The 10× roadmap (phased, additive — reuses L0–L6 + dashboard + governance)

- **Phase A — Regulatory unlock (must-have):** RFA lifecycle state machine + submission channels (FMR/CRILC/CFR/**FIU STR-CTR**) + **FRI/DPIP/MuleHunter** connectors (SCAFFOLD) + **golden-hour freeze queue** + model **kill-switch** + 7-dim model validation. *Without these a PSB cannot deploy.*
- **Phase B — Customer/payment axis (the scope 10×):** customer/account L0 events + **real-time UPI/IMPS scorer** + **mule-account network scoring** + **AePS/BC monitoring** + the **L6.5 decision engine** (hold/step-up/soft-decline).
- **Phase C — Customer loop + intelligence:** outlier pre-confirmation + EBT zero-liability workflow + vernacular two-way alerts + consortium feeds (DPIP/NPCI/I4C) + device/endpoint telemetry + digital-arrest detector + CIMS/KYC-due trackers.

## 2.8 Honest framing

Almost all of this **reuses what we already built** — the same L0→L6 funnel, dashboard, RBAC, tokenization, WORM audit, and governance — applied to a **customer/payment axis** plus an **India-integration layer**. The external connectors (DPIP, FRI, MuleHunter, CFCFRMS, FINnet 2.0, NPCI, CFR) are **SCAFFOLD until the bank provides credentials/connectivity** — the exact pattern as our existing CBS/SWIFT/PAM connectors. **Alert-only is preserved**; the new decision engine adds reversible *transaction* friction, distinct from *person* classification. The net effect: from "an excellent insider-fraud prototype" to "**a deployable, RBI-aligned, customer-and-insider fraud platform a PSB like Union Bank can actually run.**"

---

*Part 2 basis: live web research (Jun 2026) — RBI Master Directions on Fraud Risk Management 2024; RBI FREE-AI report (Aug 2025) + draft MRMF 2026; RBIH MuleHunter.AI; RBI DPIP; DoT FRI advisory (30 Jun 2025); RBI AePS Touchpoint-Operator Directions (in force 1 Jan 2026); RBI Authentication Directions 2025 (eff. 1 Apr 2026); MHA/I4C CFCFRMS-NCRP-1930 SOP (2 Jan 2026); FIU-IND FINnet 2.0; NPCI 2025 UPI FRM; Supreme Court digital-arrest directive (Feb 2026); Union Bank of India CBS/merger context. Status mapped against our actual `ml/`, `backend/regulatory/`, and `data/` code.*
