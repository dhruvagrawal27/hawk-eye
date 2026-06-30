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

# PART 2 — Making it 10× More Useful for a PSB (Union Bank of India) — INSIDER / PRIVILEGED-USER scope

> **Scope-corrected & rewritten (replaces the earlier customer-fraud version).** This platform watches **internal / privileged bank staff** — DBAs, sysadmins, SWIFT/treasury operators, ops makers & checkers, loan officers, IAM/PAM admins, and bank-side agents (BC/AePS operators). It is **NOT** a customer / account / transaction-fraud system: we do **not** score customer payments, UPI/AePS customer flows, or mule accounts as customer entities. The 10× here is **going deeper and wider on the privileged-user surface** and wrapping it in the RBI **staff-fraud + AI-governance** machinery a PSB is audited against. Where customer fraud is *enabled by an insider* (a staffer opening mule accounts, suppressing AML alerts, bypassing KYC, leaking data), the in-scope signal is **"which insider did it,"** never scoring the customer.

## 2.0 The 10× thesis (corrected)

Not a new customer axis. The 10× is four moves, all reusing L0→L6 + dashboard + governance:
**(A)** deepen the **privileged-action detection surface** (PAM command-level, SWIFT/treasury, DBA god-mode, entitlement/JML); **(B)** add the **PSB-specific insider typologies** beyond our 12; **(C)** add a **privileged-action interdiction step** (hold / step-up a risky *staff action* for a second approver — distinct from auto-blocking money); **(D)** wrap it in the **RBI staff-accountability + FMR/CFR + FREE-AI model-governance** machinery. *Deepen the insider surface — don't broaden to customers.*

## 2.1 Go deeper on the privileged surface (the core 10×)

| Area | What to add | Our status |
|---|---|---|
| **PAM session-content depth** (CyberArk/BeyondTrust) | Not just "a privileged session happened" — parse **command/query-level** activity: keystroke/command anomaly, which tables were touched, mass `SELECT`/export, config changes during the session | PARTIAL (we flag sessions + DB-layer; add content parsing) |
| **SWIFT / treasury / trade-finance operator** (the PNB seam) | SWIFT↔CBS recon (HAVE) **+** LoU/LC issuance vs sanctioned limits, nostro reconciled by the same operator, dealer blotter late/cancel-rebook (HAVE rogue-trader) — deepen for treasury insiders | PARTIAL |
| **DBA / sysadmin "god-mode"** | Direct DB write w/o app-txn (HAVE), audit-log/config tampering (HAVE proxy), **service/shared/orphaned-account abuse, standing-privilege, dormant-privileged reactivation** | PARTIAL |
| **Entitlement / IGA / JML depth** | Self-grant (HAVE) + toxic-combination matrix (HAVE) + **JIT/least-privilege gaps, access-recertification misses, standing-privilege-reduction recommendations** | PARTIAL |
| **Maker-checker / four-eyes collusion at scale** | L5 rings (HAVE) extended to recurring-pair + circular-approval **across the merged Finacle CBS** (ex-Union/Andhra/Corporation) | PARTIAL |
| **Continuous per-user insider risk index** | A live risk score per privileged user tied to **HR events** (notice period, grievance, role change, no-leave-taken streak) + access posture + recent anomalies | MISSING (compose from existing features) |

## 2.2 PSB-specific insider typologies to add (beyond our 12)

- **Officer–borrower collusion in loan sanction** — insider appraiser = borrower; inflated valuation; disbursement to a non-sanctioned account (deepen our ghost-loan/appraisal — detected as the *officer's* behaviour, not borrower-account EWS).
- **Insider-enabled mule onboarding** — a teller/BC/ops user **opening clusters of accounts that later turn mule, or over-riding KYC**, detected as a **staff anomaly** (account-open velocity, KYC-override rate, same-device onboarding) — *not* by scoring the customer.
- **Insider AML alert suppression** (HAVE `alert_suppression`) — deepen: per-analyst clear-rate, reopen-then-clear, improper closure.
- **Insider data exfiltration / leakage to external fraudsters** (the bridge) — bulk export (HAVE) + screen capture, OTP/credential leakage, **disabling of controls/2FA** that enables downstream customer fraud.
- **Privileged-user-assisted account takeover** — an insider who silently resets a customer's credentials, enrolls a channel, or disables 2FA: the in-scope signal is the **staff action**, not the takeover outcome.
- **Vendor/procurement insider fraud** (fake vendor = employee — HAVE), **SWIFT/LoU insider issuance** (PNB — HAVE).

## 2.3 Privileged-action interdiction — reconciled with alert-only

Reframed for **staff actions**, not customer transactions. Add an `L6.5` policy on a *privileged action* (entitlement self-grant, SWIFT message, bulk export, direct DB write, maker+checker by the same actor) →
`{ ALLOW · STEP_UP (mandatory second-approver / re-auth) · HOLD_FOR_REVIEW (time-boxed, pending maker-checker) }`.
This is a **control on a reversible staff action** with a human in the loop — fully consistent with **alert-only + natural justice** (we still never auto-*classify a person* as a fraudster, per SBI v. Rajesh Agarwal). High value, squarely in scope. *(This replaces the earlier customer-transaction decision engine.)*

## 2.4 The RBI wrapper that applies to INSIDER / STAFF fraud

| Mandate (2024–2026) | Why it applies to *insider* fraud | Add | Priority |
|---|---|---|---|
| **RBI Master Directions on Fraud Risk Management 2024** | Insider/staff frauds we detect go through the same lifecycle | **RFA lifecycle state machine**, **staff-accountability examination (6-month clock)**, SCBMF board pack, natural-justice show-cause | must-have |
| **FMR + Central Fraud Registry (CFR)** | Staff fraud incidents are FMR-reported and fed to CFR | Case-lifecycle-driven FMR generation + **submission channel** (SCAFFOLD); CFR feed of confirmed insider frauds | must-have |
| **RBI Cyber Security Framework + IS Audit** | Insider-threat controls are inspected (privileged access, SoD, log integrity) | Auto-produce the **insider-control evidence pack** auditors check | high |
| **RBI FREE-AI (Aug 2025) + draft Model Risk Mgmt (MRMF, 2026)** | Our ML models are a regulated, inspectable class | **Model kill-switch** per model + 7-dimension validation + risk-tiering in the registry | must-have |

*Out of scope now (customer/credit, not staff): borrower-EWS, CRILC large-exposure, FIU customer STR, customer notification/liability, golden-hour customer freeze, MuleHunter/DPIP/FRI customer feeds.*

## 2.5 Union-Bank-of-India specifics (insider lens)

- **Merged Finacle CBS silos**: monitor privileged users, maker-checker pairs, and entitlements across **ex-Union / Andhra / Corporation** instances; resolve **one staff identity** across the merged AD/HR/IAM — extend `data/mdm/entity_resolution.py` to the unified *staff* master (not a customer master).
- **BC / AePS operators as bank-side privileged agents** (the one "channel" item that *is* in scope, because the **operator** is internal-adjacent): per-terminal velocity, biometric-failure clustering, withdrawal-only patterns — scored as a **staff/agent** anomaly, never as customer-account fraud.
- **Scale**: ~8,000+ branches and thousands of privileged users → per-entity/per-peer baselines, peer-fair scoring, and **alert budgeting** matter even more.
- **Vernacular investigator narratives** (Hindi/regional) via the existing TEE-LLM gateway.
- **On-prem / India residency** — already **HAVE** (OPA/Conftest gates, Vault/HSM, retention windows).

## 2.6 The 10× roadmap (insider-scoped, additive)

- **Phase A — deepen detection:** PAM session-content, SWIFT/treasury, DBA god-mode, entitlement/JML depth, continuous per-user insider risk index + the new PSB insider typologies.
- **Phase B — privileged-action interdiction & scale:** the `L6.5` step-up/hold engine + maker-checker-collusion across the merged CBS + BC/AePS-operator monitoring.
- **Phase C — RBI wrapper:** RFA lifecycle + staff-accountability + FMR/CFR generation & submission + FREE-AI model kill-switch + IS-audit evidence pack + vernacular narratives.

## 2.7 Honest framing

Everything here **reuses L0→L6 + the dashboard + governance** — it *deepens the insider/privileged surface* and adds the **RBI staff-fraud + AI-governance wrapper**; it does **not** turn us into a customer-transaction system. External hooks (PAM content, IGA, FMR/CFR submission) are **SCAFFOLD until the bank wires credentials** — the same pattern as our existing CBS/SWIFT/PAM connectors. **Alert-only is preserved**; the new step-up/hold is a control on a *reversible staff action*, not an auto-block of money, and a person is still classified only by a human after a hearing.

---

*Part 2 (rescoped to insider / privileged-user only, per the corrected problem statement) basis: RBI Master Directions on Fraud Risk Management 2024 (RFA, staff-accountability, FMR, CFR, natural justice / SBI v. Rajesh Agarwal); RBI Cyber Security Framework + IS Audit; RBI FREE-AI report (Aug 2025) + draft MRMF 2026 (model kill-switch, 7-dimension validation); Union Bank of India merged-Finacle/scale context. Customer/account/transaction-fraud capabilities were removed as out of scope. Status mapped against our actual `ml/`, `backend/regulatory/`, `data/` code.*
