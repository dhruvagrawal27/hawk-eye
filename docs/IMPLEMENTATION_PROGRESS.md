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
| 1 | Detection Transparency — real 5-layer fusion decomposition (raw scores, SoD, agreement, rescued-by) | 1 | Investigator / model-eng | 🔧 in progress |
| 2 | Rich explainability — structured L5 graph render, L4 attention heatmap, SHAP value/percentile | 1+3 | Investigator | ⏳ pending |
| 3 | Entity-360 deep dive — off-hours heatmap, peer deep stats, per-layer score timeline | 2+3 | Investigator | ⏳ pending |
| 4 | Sub-threshold / ambient activity — the literal <70 "95%" recorded-not-alerted feed | 2 | Management / investigator | ⏳ pending |
| 5 | Management analytics — typology prevalence + confirmed-rate, detection funnel, disposition analytics | 2 | Management | ⏳ pending |
| 6 | Governance & trust — per-layer model lineage, drift depth, real TEE proof detail | 2 | Model-eng / auditor | ⏳ pending |

---

## Phase 1 — Detection Transparency
**Goal:** turn the client-side fusion *fiction* (hardcoded 3-layer weights, no backend source) into the **real 5-layer fusion arithmetic** delivered by the backend: each layer's raw 0–1 score, the meta-learner coefficient, weighted contribution, the SoD component, the fused probability vs the decision threshold, cross-layer **agreement**, and an honest **decisive-layer / "rescued-by"** counterfactual.

### Task ledger
- [ ] `backend/fusion/calibration.py` — expose `agreement_from(layer_scores)` (factor out of `confidence_from`).
- [ ] `backend/fusion/service.py` — enrich `FusionOutput` (`layer_scores`, `layer_weights`, `sod`, `agreement`, `threshold`, `decisive_layer`, `rescued`); add `build_breakdown(...)`; populate in `fuse()`.
- [ ] `backend/services/api/app/schemas/alerts.py` — internal `fusion_breakdown` field (excluded from wire).
- [ ] `backend/services/api/app/pipeline/online.py` — attach breakdown on **all three** emit paths (fused / L1 short-circuit / degraded).
- [ ] `backend/services/api/app/schemas/explanations.py` — `FusionComponent` + `FusionBreakdown`; add `fusion` to `Explanation`.
- [ ] `backend/services/api/app/routes/explanation_routes.py` — return `fusion` (stored breakdown, else honest fallback synthesis).
- [ ] `backend/tests/...` — fusion-breakdown + explanation-contract test.
- [ ] `frontend/src/lib/types.ts` — extend `FusionComponent`/`FusionBreakdown`/`FusionLayer` (additive).
- [ ] `frontend/src/components/ScoreComposition.tsx` — 5-layer meta, agreement readout, backend-sourced.
- [ ] `frontend/src/lib/layerFusion.ts` — `normLayer` L1_rule↔L1_rules; consume backend agreement.
- [ ] `frontend/src/lib/mocks/handlers.ts` — `buildFusion` → 5-layer breakdown + agreement (keep worked-burst rescue story).
- [ ] Gates: `tsc`, `eslint --max-warnings=0`, `vitest`, backend tests.
- [ ] CONTEXT.md entry + this file.

_Status log (newest first):_
- 2026-07-01 — Phase 1 kicked off; seam mapped (fusion computes per-layer scores/SoD/agreement then discards them; FE `FusionBreakdown` is a 3-layer client-side synthesis). Tracker created.
