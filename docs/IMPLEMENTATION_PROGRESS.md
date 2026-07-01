# Hawk-Eye — "Surface the Hidden 95%" Implementation Progress

> **Living tracker.** Updated at every step of the UI/UX + data-surfacing overhaul. Newest phase status at the top of each section. Companion to `CONTEXT.md` (the cross-workstream decision log) — this file is the fine-grained task/progress ledger for the surfacing overhaul.

## Mandate (approved 2026-07-01)
The 8-layer engine (L0–L7) computes far more than reaches a screen. The "~5% displayed" gap is real and leaks at **three boundaries**:
1. **ML → Alert (truncation at fusion):** raw per-layer scores (L1–L5), SoD flag, fused probability, cross-layer agreement, L4 attention matrices, full L3 SHAP vectors, the typed L5 graph + per-edge attribution — all collapsed to `contributing_layers` (enum names) + ≤6 reason codes.
2. **Storage → API (never queried):** `EMIT_THRESHOLD = 70` drops every sub-70 scored event to ClickHouse unseen; `hawkeye.scores` (per-event × per-layer × model_version), disposition/typology analytics, and the report archive are never aggregated.
3. **API → UI (under-visualized):** L5 graph rendered as text; no per-layer probability decomposition; L4 attention reduced to one bar.

**Decisions:** broad overhaul · all personas · balanced wow+utility · backend free to add/enrich · **phased with gates** · existing `apiClient` + MSW-mock/live-toggle seam (wire real where cheap).

**Invariants preserved every phase:** alert-only (no auto-block/classify) · RBAC 8×9 · PII tokenized · every alert ≥1 reason code · time UTC-stored/IST-shown · INR integer minor units · synthetic/honest labeling.

**Gate discipline (no process skipped):** each phase ships `schema → service/pipeline → route → backend test → FE types → apiClient → component(s) → MSW mock/fixture → FE test → gates (tsc/eslint/vitest[/build]) → CONTEXT.md + this file`.

---

## Phase roadmap
| Phase | Theme | Boundary | Persona | Status |
|---|---|---|---|---|
| 1 | Detection Transparency — real 5-layer fusion decomposition (raw scores, SoD, agreement, rescued-by) | 1 | Investigator / model-eng | ✅ **done** (all gates green) |
| 2 | Rich explainability — L4 attention heatmap (variable×temporal) + SHAP peer percentile (L5 chips already structured; inline mini-graph deferred) | 1+3 | Investigator | ✅ **done** (all gates green) |
| 3 | Entity-360 deep dive — 7×24 off-hours activity heatmap + timeline `is_off_hours` (per-layer score timeline deferred) | 2+3 | Investigator | ✅ **done** (all gates green) |
| 4 | Sub-threshold / ambient activity — detection funnel + near-miss watchlist (`GET /activity/sub-threshold`) | 2 | Management / investigator | ✅ **done** (all gates green) |
| 5 | Management analytics — fraud-typology prevalence + confirmed-rate + exposure (`GET /analytics/typologies`) | 2 | Management | ✅ **done** (all gates green) |
| 6 | Governance & trust — per-layer model lineage + posture on the alert (`explanations.model_lineage`) | 2 | Model-eng / auditor | ✅ **done** (all gates green) |

---

## Phase 1 — Detection Transparency
**Goal:** turn the client-side fusion *fiction* (hardcoded 3-layer weights, no backend source) into the **real 5-layer fusion arithmetic** delivered by the backend: each layer's raw 0–1 score, the meta-learner coefficient, weighted contribution, the SoD component, the fused probability vs the decision threshold, cross-layer **agreement**, and an honest **decisive-layer / "rescued-by"** counterfactual.

### Task ledger
- [x] `backend/fusion/calibration.py` — exposed `agreement_from(layer_scores)` (factored out of `confidence_from`).
- [x] `backend/fusion/service.py` — enriched `FusionOutput` (`layer_scores`, `sod`, `agreement`, `breakdown`); added `LAYER_META_WEIGHTS`, `DECISION_THRESHOLD_PROB`, `build_breakdown(...)`; populated in `fuse()`.
- [x] `backend/services/api/app/schemas/alerts.py` — internal `fusion_breakdown` field (excluded from wire).
- [x] `backend/services/api/app/pipeline/online.py` — breakdown attached on **all three** emit paths (fused / L1 short-circuit / degraded).
- [x] `backend/services/api/app/schemas/explanations.py` — `FusionComponent` + `FusionBreakdown`; `fusion` added to `Explanation`.
- [x] `backend/services/api/app/routes/explanation_routes.py` — returns `fusion` (stored breakdown, else honest fallback synthesis).
- [x] `backend/tests/unit/test_fusion_breakdown.py` — builder math, rescue logic, `fuse()`, endpoint contract (6 tests).
- [x] `frontend/src/lib/types.ts` — extended `FusionComponent`/`FusionBreakdown`/`FusionLayer` (additive).
- [x] `frontend/src/components/ScoreComposition.tsx` — 5-layer meta, agreement readout, decisive-layer rescue callout, backend-sourced.
- [x] `frontend/src/lib/layerFusion.ts` — `normLayer` L1_rule↔L1_rules; consumes backend threshold/rescued/decisive/agreement.
- [x] `frontend/src/lib/mocks/handlers.ts` — `buildFusion` → 5-layer breakdown + agreement (worked-burst rescue story preserved).
- [x] `frontend/src/components/ScoreComposition.test.tsx` + fusion assertion in `payloads.contract.test.ts`.
- [x] Gates: backend **153 pytest** · FE **157 vitest** · `tsc` clean · `eslint` 0 warnings · `vite build` ok.
- [x] CONTEXT.md entry + this file.

_Status log (newest first):_
- 2026-07-01 — **Phase 1 DONE.** Real 5-layer fusion decomposition now flows ML→L6→API→UI. Every alert carries the per-layer raw scores + meta weights + weighted contributions + cross-layer agreement + decisive-layer/rescued-by, served on `GET /explanations/{id}.fusion` and rendered in `ScoreComposition`. All gates green.
- 2026-07-01 — Phase 1 kicked off; seam mapped (fusion computes per-layer scores/SoD/agreement then discards them; FE `FusionBreakdown` was a 3-layer client-side synthesis). Tracker created.

---

## Follow-on rounds — all shipped to `main` + deployed (hawk-eye.nineagents.in)

**Phases 2–6 (surface the hidden 95%)** — ✅ all done, gates green:
- **P2 Rich explainability** — L4 variable×temporal **attention heatmap** + **SHAP peer percentile**; explanation carries `sequence_attention[].variables[]` and `shap[].percentile`.
- **P3 Entity-360 deep dive** — 7×24 **off-hours activity heatmap** + timeline `is_off_hours`.
- **P4 Sub-threshold ("hidden 95%")** — `GET /activity/sub-threshold`: detection funnel + near-miss watchlist; pipeline records every fully-scored event.
- **P5 Management analytics** — `GET /analytics/typologies`: typology prevalence + confirmed-rate + exposure.
- **P6 Governance & trust** — per-layer **model lineage** on `GET /explanations/{id}` (`model_lineage[]`), signature/tier/reviewer.

**Deferred polish** — ✅ inline **L5 graph mini-map** SVG in the explanation (structured `graph` nodes/edges); **per-layer score timeline** `GET /entities/{id}/layer-scores`.

**Stakeholder round (live-site feedback)** — ✅ live stream **≥50 eps** (backend `HAWKEYE_STREAM_RATE=50` + batched tape); **hundreds** of alerts via bulk seed + server-side `GET /alerts/stats`; Live Event Tape **colour legend** + clarified pause (display-only); **6-layer** fusion flow (idle layers ghosted, not hidden); ambient panel rewritten in **plain English** + friendly signal-name map; sub-threshold funnel scaled to a realistic bank-week.

**Compliance oversight UX** — ✅ per-tab "what this is" framing; **informed approvals** (inline why-flagged + expandable evidence + **activity log** + link to full alert); **clickable/interpretable department rollup** (drill-in + tooltips); **activity log on L6.5 interdiction cards** (`EmployeeActivitySummary`: risk-index + recent activity + audit "who has looked"); export download tooltip.

**Docs/metadata refresh** — ✅ README (live URL, 8-layer stack, tech stack, endpoints, run steps; removed stray junk); `docs/openapi-index.md` (+~20 newer routes, +L6.5 action-gate surface). GitHub repo description/homepage/topics: **pending owner** (the CI/gh account has WRITE, not ADMIN — owner `dhruvagrawal27` must set them).
