# Hawk-Eye — Insider/Privileged 10× Implementation Plan

> **Status:** DRAFT for review · **Scope:** Phase A detection depth + full L6.5 interdiction epic
> **Emphasis:** balanced (quick wins first) · **Feeds:** synthetic-first (external SCAFFOLD)
> **Provenance:** derived by ground-truthing `docs/DESIGN_UPGRADE_STUDY.md` (PART 2) against the
> actual codebase (every claim verified to file+symbol), then a judge-panel design of the L6.5
> architecture + per-item specs. Supersedes the study's status estimates where they differed
> from verified code (see *Doc corrections* below).

## Doc corrections (verified against code)

| Study said | Verified reality |
|---|---|
| Per-user risk index "MISSING" | Inputs mostly exist (`no_leave_taken_streak`, `notice_period`, `role_change_recency`, `dormant_reactivation`); only **grievance** signal + the **aggregation** are missing |
| Officer–borrower collusion "PARTIAL" | **HAVE** at slow-lane (`score_ghost_loan`: `appraiser_is_borrower`, `disbursement_to_non_sanctioned`); only a fast-lane velocity rule is missing |
| RFA "HAVE / add lifecycle" | `rfa.py` is a **boolean tag only** — no state machine, no clock, no DB table |
| Maker-checker rings "HAVE" | Transaction-cycle detection HAVE; **approval-authority rings MISSING** |
| Dealer-blotter cancel-rebook "HAVE" | **PARTIAL** — injected by sim, but no clustering feature |
| LoU/LC vs limits "PARTIAL" | **Effectively MISSING** — only an `instrument='LoU'` label; no limits master (feed-gated) |
| FMR/CFR "must-have add" | Generators are **real**; only live submission is SCAFFOLD; CFR just needs a route |
| Entity resolution "extend to staff master" | **Already** employee/staff-keyed across CBS/HR/IAM; real gap is multi-CBS-instance tags |

---

## Hawk-Eye — Phase A Detection Depth + Full L6.5 Interdiction Epic

### Overview

This plan sequences twelve work-items into three milestones under a **balanced** emphasis: ship quick wins first (M1), then interleave detection-depth with the audit track (M2), then build the full L6.5 Privileged-Action Interdiction epic (M3). Every item respects the codebase's existing patterns (RulesEngine hot-reload + predicate registry, `should_tag_rfa`/`tag` regulatory helpers, FastAPI route modules with `require_role` RBAC + `AUDIT.write`, governance DB SQLAlchemy `Base` models, four-eyes `check_four_eyes`/`check_disposition` guards, `reliability.CircuitBreaker`/idempotency).

**Alert-only invariant (golden rule) is preserved end-to-end and called out per item:** L1/L2/L3 only *emit alerts*; regulatory reports are SCAFFOLD (no live submission); the kill-switch *degrades scoring* but never blocks money; the RFA lifecycle *classifies a person only after a hearing* (SBI v Rajesh Agarwal show-cause gate); the L6.5 gate governs only **reversible STAFF actions**, never money movement, and Hawk-Eye is **policy-author + audit-sink only** — the SCAFFOLD source system enforces locally.

### The L6.5 Architecture Decision (locked)

L6.5 is a **synchronous Policy-Decision-Point microservice** at [services/action-gate/](services/action-gate/) on port **8096**, modeled on the existing [services/hitl-gate/](services/hitl-gate/) and [services/pam-shim/](services/pam-shim/) skeletons. It returns **`ALLOW | STEP_UP | HOLD_FOR_REVIEW`** (never a bare `DENY` — the bank's lawyers must not see a hard block). The **source system enforces locally** (today: `pam-shim POST /sessions/{id}/command`; prod: CyberArk/CBS/IGA — all SCAFFOLD); Hawk-Eye authors policy and sinks hash-chained audit but **has no actuator** and never reaches outward to CBS/PAM/IGA.

- **Decision aggregation:** any `hard_gate` policy OR SoD ≥ 0.9 OR OPA deny → `HOLD_FOR_REVIEW`; any soft policy over threshold → `STEP_UP`; else `ALLOW`.
- **`ActionEvent` deliberately omits `object.amount` from gating logic** — there is *no money-movement code path*, so the gate can never block/hold/delay a payment.
- **Reuse:** `RulesEngine` predicates (hot-reload + `known_codes()` guard), `SoDMatrix.score()`, OPA `entitlement.rego`, [hitl-gate](services/hitl-gate/hitlsvc/main.py) four-eyes/DPIA HOLD queue, [rules_routes.py](backend/services/api/app/routes/rules_routes.py) propose→approve flow, [reliability/circuit_breaker.py](backend/reliability/circuit_breaker.py) + [reliability/idempotency.py](backend/reliability/idempotency.py), the existing `AUDIT.write` hash-chained writer, and `check_four_eyes`/`check_disposition` from [auth/sod.py](backend/services/api/app/auth/sod.py).
- **Degradation:** `GovernanceClient` wraps reads in a `CircuitBreaker`; on open it **fails CLOSED for privileged verbs** (`HOLD_FOR_REVIEW`, `degraded=true`) and OPEN (`ALLOW`) only for routine verbs — privileged is *never* silently allowed. OPA timeout falls back to the deterministic Python `SoDMatrix.score()` path.
- **Rejected alternatives:** inline-pipeline gate (the online pipeline runs *after* the event, so it would gate nothing and would pollute `AlertStatus`); pure bare-`DENY` PDP scattered into a non-existent `backend/routes` dir.

---

## Milestone M1 — Quick Wins (ship first)

Five low-risk, high-signal items. Each reuses an *already-implemented* feature or a one-to-one clone of an existing pattern. No new services, no new infra.

### M1.1 — `SUSPENSE_NOSTRO_LAPPING` L1 rule (effort: M)
- **Files:** [backend/rules_engine/named_rules.py](backend/rules_engine/named_rules.py), [backend/rules_engine/rules/rules.yaml](backend/rules_engine/rules/rules.yaml), [backend/regulatory/rfa.py](backend/regulatory/rfa.py)
- **Symbols:** add `suspense_nostro_lapping(ctx, cfg) -> RuleHit | None` next to `db_write_without_app_txn`; register in `NAMED_RULES` (line 181); use the `_hit(cfg, detail, score)` helper (line 169) with `score=0.91`.
- **Logic:** verb ∈ {`suspense_post`,`nostro_post`,`reconcile`}; `ctx.feat('same_person_post_and_reconcile')` true; `ctx.feat('max_aging_days') >= cfg.params['aging_days_threshold']`. Feature already computed by [transaction.py:suspense_nostro_aging](data/features/transaction.py) (line 170) which populates exactly `same_person_post_and_reconcile` + `max_aging_days`. Verb names are config-driven (`post_verbs`/`recon_verbs` params) to absorb taxonomy drift.
- **YAML:** `code=SUSPENSE_NOSTRO_LAPPING, enabled=true, severity=high, hard_hit=true, version='1.0.0', params={aging_days_threshold: 1}` under the privileged family.
- **RFA:** append `SUSPENSE_NOSTRO_LAPPING` to `_RFA_TRIGGER_CODES` (line 11) — `should_tag_rfa` already keys on this set + the `RFA_EXPOSURE_INR = 50_00_000` / risk ≥ 70 gate.
- **Tests:** `test_suspense_nostro_lapping_hard_hit`, `_fires_only_on_same_person`, `_aging_threshold` in `backend/tests/unit/test_rules_engine.py`; confirm existing `data/tests/test_features.py::test_suspense_aging_same_person` still passes.
- **Acceptance:** hard-hit fires HIGH on same-person+aging≥1d; does not fire when `same_person=false` or aging<threshold; RFA tag applies at ≥₹50L.
- **Alert-only:** emits a reason code only; `hard_hit` short-circuits to *skip ML layers*, still produces an alert, never an action.

### M1.2 — `AUDIT_CONFIG_TAMPERING` L1 rule (effort: S)
- **Files:** [backend/rules_engine/named_rules.py](backend/rules_engine/named_rules.py), [backend/rules_engine/rules/rules.yaml](backend/rules_engine/rules/rules.yaml), [backend/services/api/app/clients/feature_client.py](backend/services/api/app/clients/feature_client.py)
- **Symbols:** `audit_config_tampering(ctx, cfg) -> RuleHit | None` + `_accumulate_tampering(feature_reader, event)`; register in `NAMED_RULES`.
- **Logic:** verb ∈ {`audit_config_change`,`disable_logging`,`modify_audit`,`clear_log`}; fires only when `ctx.feat('privileged_flag')` OR `ctx.feat('is_off_hours')` (tighter gate per spec); reads decayed count `ctx.feat('log_tampering_proxy')` (already produced by [data_layer.py:log_tampering_proxy](data/features/data_layer.py) line 125). `hard_hit=false` so it contributes to L6 fusion weighting rather than short-circuiting.
- **FeatureReader:** add timestamp-keyed decay (`decay_hours`, default 24) with a bounded entity map (≤100) to avoid a memory leak; expose `log_tampering_proxy` via the existing features-dict merge (use `setdefault` to avoid key collision).
- **YAML:** `severity=high, hard_hit=false, params={tampering_count_min:1, decay_hours:24, sensitive_verbs:[...]}`.
- **Tests:** privileged+1 event fires (0.85); off-hours+1 fires (0.75); neither → None; decay to 0 after 24h; e2e through `OnlinePipeline.process`.
- **Alert-only:** signal only; no action path.

### M1.3 — `GET /reports/cfr` endpoint (effort: S)
- **Files:** [backend/services/api/app/routes/report_routes.py](backend/services/api/app/routes/report_routes.py), [backend/services/api/app/schemas/reports.py](backend/services/api/app/schemas/reports.py)
- **Symbols:** `CfrLineItem`, `CfrReport` Pydantic models (mirror `FmrReport`/`CrilcReport`); `report_cfr(principal = Depends(_COMPLIANCE)) -> CfrReport`.
- **Pattern (verbatim clone of `report_fmr`):** `_COMPLIANCE = require_role(Role.DGM_COMPLIANCE, Role.AGM_VIGILANCE)` already defined (line 23). Filter `AlertStatus.CONFIRMED_FRAUD`, call `cfr.generate_feed(confirmed, submission_enabled=settings.rbi_submission_enabled)` and `cfr.dami_summary(confirmed)` (both exist in [cfr.py](backend/regulatory/cfr.py)), then `AUDIT.write(action='report.cfr', detail={'lines': count})`.
- **Response:** `generated_ts` (ISO-Z), `submission_enabled` (SCAFFOLD default False), `items` (cfr_id/entity_id/amount_inr/category/reported_ts), `dami_summary`.
- **Tests:** RBAC 401/403, empty, payload mapping, dami aggregation, audit write, scaffold flag.
- **Alert-only / SCAFFOLD:** `submission_enabled` defaults False — no live CFR channel; report generation only.

### M1.4 — `risk_tier` on serving ArtifactMeta + registry↔inventory reconcile + tier-gated promote/load (effort: M)
- **Files create:** [backend/serving/reconcile.py](backend/serving/reconcile.py), [backend/tests/unit/test_serving_reconcile.py](backend/tests/unit/test_serving_reconcile.py)
- **Files edit:** [backend/serving/registry.py](backend/serving/registry.py), [backend/serving/loader.py](backend/serving/loader.py), [backend/serving/runtime.py](backend/serving/runtime.py) (no hot-path change — tier checks at promote/load only).
- **Symbols:** add `ArtifactMeta.risk_tier: str | None = None` (after line 33); populate in `LocalRegistry._seed()` (line 50; mappings L2=HIGH, L3=CRITICAL, L4=MODERATE, L6=CRITICAL). Add `set_stage_with_tier_gate(...)->(ArtifactMeta|None, blockers)` (leave `set_stage` line 105 unchanged for back-compat). Add `RegistryInventoryReconciler.reconcile(registry, inventory)->RegistryInventoryReport` (tier_mismatch / version_drift / validation_drift + `untracked`). Add `ModelLoader.load_production_with_tier_check(layer, inventory, enforce_high_tier)`.
- **Reuse:** `default_inventory()` + tier enums from [ml/mlops/inventory.py](ml/mlops/inventory.py); `ChangeRequest` workflow from [ml/mlops/governance/change_workflow.py](ml/mlops/governance/change_workflow.py).
- **Tests:** 10 unit tests (tier presence, critical-promote blocked/allowed-with-gate, moderate bypass, three drift detections, healthy-when-aligned, high-tier-unsigned rejected, low-tier-unsigned allowed, inventory=None bypass).
- **Alert-only:** governance hardening of the model serving path; no effect on alert emission.

### M1.5 — Grievance HR insider signal (effort: S)
- **Files create:** [tests/ml/test_grievance_feature.py](tests/ml/test_grievance_feature.py)
- **Files edit:** [data/schemas/l0_event.py](data/schemas/l0_event.py), [data/connectors/hr_iga/adapter.py](data/connectors/hr_iga/adapter.py), [data/connectors/hr_iga/fixtures.json](data/connectors/hr_iga/fixtures.json), [data/features/change_hr.py](data/features/change_hr.py), [backend/services/api/app/schemas/events.py](backend/services/api/app/schemas/events.py)
- **Symbols:** add `Actor.grievance_count: Optional[int] = None` and `Actor.grievance_recency_days: Optional[int] = None` to the dataclass (line 17) + Avro/JSON schema blocks (lines ~153). Adapter accepts `verb ∈ {file_grievance, close_grievance}` with `channel='hr'`. Add `grievance_count(df)->Series` and `grievance_recency(df)->Series` to change_hr (mirror `role_change_recency` line 90). Mirror the two fields in the backend Pydantic `Actor`.
- **Tests:** count aggregation, recency-days (NaN if none), empty df, adapter round-trip, contract/Avro+JSON validation, featurize integration.
- **Alert-only:** adds context features only; **no new rule** here (a grievance rule is a deliberate follow-on). PII-sensitive — grievance fields tokenized by the existing PII controller.
- **Why first / dependency root:** M2.1 (risk index) requires `grievance_recency`; shipping it in M1 unblocks M2.

**M1 outcome:** two new detection rules, a missing regulatory report endpoint closed, model-serving governance reconciliation, and the grievance signal that the risk index depends on — all alert-only, all on existing infra.

---

## Milestone M2 — Detection Depth × Audit Track (interleaved)

Three detection-depth items and two audit-track items. Sequenced so dependencies resolve: standing-privilege (M2.2) and grievance (M1.5) feed the risk index (M2.1); PAM content (M2.3) yields richer signals later consumed by L6.5.

### M2.2 — Standing-privilege detection (effort: M) — *do before M2.1*
- **Files:** [data/features/identity_access.py](data/features/identity_access.py), [backend/rules_engine/privileged.py](backend/rules_engine/privileged.py), [backend/rules_engine/rules/rules.yaml](backend/rules_engine/rules/rules.yaml)
- **Symbols (features, mirror `entitlement_change_velocity` line 213):** `entitlements_unexercised_90d(df, window_days=90)`, `entitlements_unexercised_180d(df, window_days=180)`, `days_since_grant_max(df)`, `never_exercised_entitlements(df)`.
- **Rule:** `standing_privilege_detection(ctx, cfg) -> RuleHit | None` in privileged.py; register in `PRIVILEGED_RULES` (line 83). Fires when (`never_exercised` OR `unexercised_90d >= threshold`) AND `days_since_grant_max >= min_grant_age_days`; `severity=medium, hard_hit=false, score=0.65`.
- **YAML:** `STANDING_PRIVILEGE_DETECTION` with `exercise_verb_mapping`, `unexercised_90d_threshold=2`, `min_grant_age_days=14`, `window_days=90`.
- **Wiring:** the four features flow through `ml/adapters/featurize.py` entity-level features → `feature_source.online_features` → `RuleContext.feat`. `RulesEngine` already merges `NAMED_RULES + PRIVILEGED_RULES`, so no engine change.
- **Tests:** per-feature unit tests; predicate threshold/timing tests; featurize column-presence assertions.
- **Risk:** entitlement revocation not tracked in L0 — document the "held set" assumption; tune windows on labeled data.
- **Alert-only:** medium-severity signal only.

### M2.1 — Continuous per-user insider-risk index (effort: M) — *needs M1.5 + M2.2*
- **Files create:** [ml/pipelines/insider_risk_index.py](ml/pipelines/insider_risk_index.py), [backend/services/api/app/schemas/risk_index.py](backend/services/api/app/schemas/risk_index.py), [frontend/src/components/RiskIndexGauge.tsx](frontend/src/components/RiskIndexGauge.tsx), [tests/ml/test_insider_risk_index.py](tests/ml/test_insider_risk_index.py)
- **Files edit:** [data/feature_store/feature_repo/repo.py](data/feature_store/feature_repo/repo.py), [data/features/identity_access.py](data/features/identity_access.py), [data/features/change_hr.py](data/features/change_hr.py), [backend/services/api/app/routes/entity_routes.py](backend/services/api/app/routes/entity_routes.py), [backend/services/api/app/schemas/entities.py](backend/services/api/app/schemas/entities.py), [backend/services/api/app/store/entity_store.py](backend/services/api/app/store/entity_store.py), [frontend/src/components/Dashboard.tsx](frontend/src/components/Dashboard.tsx)
- **Symbols:** `InsiderRiskIndex` (hr/access/anomaly/composite + sub_scores + `RiskExplanation`), `compute_insider_risk_index(events, alerts_30d, store) -> dict[emp_id, InsiderRiskIndex]`, `RiskIndexResponse`, `EMPLOYEE_RISK_INDEX` FeatureView (1h TTL). Endpoint mounted as `GET /users/{emp_id}/risk-index` in entity_routes (reuses `Capability.VIEW_ALERTS` + `_view_audit`). `EntityStore.put_risk_index/get_risk_index`.
- **Composition:** weighted (HR 30% / access 35% / anomaly 35% — stub weights, flagged for calibration), peer-fairness via role z-score clamp [-3,+3]. Inputs: `no_leave_taken_streak`, `notice_period`, `role_change_recency`, **`grievance_recency` (M1.5)**, `entitlement_change_velocity`, **`standing_privilege` (M2.2)**, `dormant_reactivation`, `offhours_score`, recent alert counts.
- **Tests:** composite 0–100 + monotonicity + peer-clamp; route integration with seeded store + audit; contract test for the new schema.
- **Risk:** weights are stubs (require labeled ground truth); peer-fairness can suppress alerts in fraud-concentrated cohorts → **HITL review required**.
- **Alert-only:** a *displayed score with explanation*; never an automated action.

### M2.3 — PAM session-content command parsing (effort: L)
- **Files create:** [data/features/pam_session.py](data/features/pam_session.py), [data/connectors/iam_pam/command_parser.py](data/connectors/iam_pam/command_parser.py), [backend/rules_engine/pam_predicates.py](backend/rules_engine/pam_predicates.py), [tests/test_pam_parser.py](tests/test_pam_parser.py)
- **Files edit:** [data/connectors/iam_pam/adapter.py](data/connectors/iam_pam/adapter.py), [data/features/data_layer.py](data/features/data_layer.py), [ml/adapters/featurize.py](ml/adapters/featurize.py), [backend/rules_engine/privileged.py](backend/rules_engine/privileged.py), [backend/rules_engine/rules/rules.yaml](backend/rules_engine/rules/rules.yaml)
- **Symbols:** `CommandParser.parse(command_str, dialect='auto')->ParsedCommand` (verb/type/tables_touched/rowcount/is_export_flag/anomaly_score); `SessionCommandAnalyzer.analyze(session_id, commands)->SessionFeatures`; features `pam_command_velocity`, `pam_tables_touched`, `pam_ddl_chain_anomaly`, `pam_mass_select_export`; rules `mass_export_from_privileged_session`, `ddl_chain_anomaly` registered in `PRIVILEGED_RULES`.
- **Constraint:** parser is **opaque-string-agnostic, no keylogging** — operates on recorded shell/SQL verbs only, consistent with the pam-shim contract (commands stored as opaque strings per `tests/test_pam_shim.py`). Cache parsed results per session_id; batch-parse offline to keep online latency low.
- **YAML:** `PAM_MASS_SELECT_EXPORT`, `PAM_DDL_CHAIN_ANOMALY` — `severity=medium, hard_hit=false`, tunable `rowcount_threshold`/`ddl_window_seconds`/`velocity_threshold`; gate DDL anomaly behind a `role != dba` filter to suppress legitimate migration scripts.
- **Tests:** parser unit (SELECT/export/DDL-cascade/GRANT-chain), analyzer velocity, feature tests on demo_frame, predicate tests, featurize shape/type, online-pipeline integration.
- **Feeds forward:** richer PAM signals (`bulk_export_high_volume`, mass-select) become L6.5 predicate inputs in M3.
- **Risk:** parser brittleness on non-standard dialects → fall back to verb-only partial parse; coordinate with existing `PRIVILEGED_SESSION_CORRELATION` to avoid double-counting.
- **Alert-only:** two new alert rules; **real PAM feed integration is SCAFFOLD** — synthetic fixtures only.

### M2.4 — Per-model kill-switch (runtime DISABLED, no redeploy) (effort: L)
- **Files create:** [backend/serving/model_state.py](backend/serving/model_state.py), [backend/services/api/app/schemas/model_state.py](backend/services/api/app/schemas/model_state.py), [backend/services/api/app/clients/model_state_client.py](backend/services/api/app/clients/model_state_client.py), [backend/services/api/app/routes/model_disable_routes.py](backend/services/api/app/routes/model_disable_routes.py), [governance/db/seed_model_state.py](governance/db/seed_model_state.py)
- **Files edit:** [backend/serving/registry.py](backend/serving/registry.py), [backend/serving/runtime.py](backend/serving/runtime.py), [backend/serving/loader.py](backend/serving/loader.py), [ml/mlops/inventory.py](ml/mlops/inventory.py), [backend/services/api/app/schemas/models.py](backend/services/api/app/schemas/models.py), [backend/services/api/app/clients/registry_client.py](backend/services/api/app/clients/registry_client.py), [backend/services/api/app/routes/model_routes.py](backend/services/api/app/routes/model_routes.py), [governance/db/models.py](governance/db/models.py), [governance/db/schema.sql](governance/db/schema.sql)
- **Symbols:** `ModelState` enum (ENABLED/DISABLED); `ModelDisabledRecord`; `ModelStateStore` (in-mem snapshot + governance DB persistence); `InferenceRuntime.score()` guard `_check_disabled_models(layers)` that skips disabled layers into `result.degraded_layers` (reuses the existing `degraded_layers` field, line 24); `ModelLoader.load_production` returns None when `ArtifactMeta.disabled`; routes `POST /models/{id}/disable`, `/enable`, `GET /models/{id}/state` gated by a new `MODEL_KILL_SWITCH` capability (DGM_COMPLIANCE/AGM_VIGILANCE/CGM_RISK/IT_ADMIN); governance `ModelDisableAudit` + `model_state` tables (`CREATE TABLE IF NOT EXISTS`, portable SQLite/Postgres via `Base`); `InventoryEntry.operational_state`; `ArtifactMeta.disabled: bool = False`.
- **Fallback (alert-only):** disabling a layer degrades to remaining layers; **L1 rules are never disableable** so an alert always survives (L3 disabled → L2+L4 still score; all ML disabled → L1-rules-only). `set_disabled` is atomic (in-mem set + DB insert); in-flight scores use start-of-execution state. Reconcile inventory→DB on startup.
- **Tests:** state store CRUD + persistence; route RBAC (403/200); score skips disabled layer; degradation to remaining layers and to L1-only; loader respects flag; audit immutability; no-redeploy toggle; seed all-enabled.
- **Audit-track tie-in:** every toggle writes `AUDIT.write(action='model.disable'|'model.enable')` with actor/approver/reason/ts.
- **Alert-only:** kill-switch *halts a scorer*, never blocks money; system never crashes on full ML disable.

### M2.5 — RFA lifecycle state machine + 6-month examination clock (effort: XL)
- **Files create:** [backend/regulatory/rfa_lifecycle.py](backend/regulatory/rfa_lifecycle.py), [backend/services/api/app/routes/rfa_routes.py](backend/services/api/app/routes/rfa_routes.py), [backend/services/api/app/schemas/rfa.py](backend/services/api/app/schemas/rfa.py)
- **Files edit:** [governance/db/schema.sql](governance/db/schema.sql), [governance/db/models.py](governance/db/models.py), [backend/regulatory/rfa.py](backend/regulatory/rfa.py), [backend/services/api/app/routes/report_routes.py](backend/services/api/app/routes/report_routes.py), [backend/services/api/app/routes/disposition_routes.py](backend/services/api/app/routes/disposition_routes.py)
- **Symbols:** `RfaExamination(Base)` table (`UNIQUE(entity_id)`); `RfaState` enum (TRIGGERED/UNDER_EXAMINATION/CONFIRMED/CLOSED); `RfaTransitionValidator.validate_transition(...)`; `RfaLifecycleService` (`trigger`, `transition_to_examination`, `show_cause_request`, `close_examination`, `check_window_expiry`); routes `POST /rfa/{entity_id}/examination`, `/show-cause`, `/close`, `GET /rfa/{entity_id}`; `is_rfa_triggered(entity_id, session)`. Reuse `add_days`/`parse`/`iso_z` from [regulatory/util.py](backend/regulatory/util.py).
- **Clock:** `examination_due_ts = triggered_ts + 180d`, `show_cause_due_ts = triggered_ts + 30d`. **Close requires** state=UNDER_EXAMINATION AND `show_cause_response_ts` not null (natural-justice gate) AND `now < examination_due_ts`.
- **Trigger point:** in `disposition` handler ([disposition_routes.py](backend/services/api/app/routes/disposition_routes.py) line 73), on `outcome='fraud'` call `RfaLifecycleService.trigger(...)` **before** `ALERTS.record_disposition` (atomic ordering). Keep `rfa.tag()`/`should_tag_rfa` unchanged for FMR/CRILC back-compat; FMR/CRILC line items join `rfa_examinations` for `rfa_state`/`examination_due_ts`/`window_expired`.
- **RBAC/SoD:** all `/rfa/*` routes require DGM_COMPLIANCE or AGM_VIGILANCE; model-deployer capabilities cannot initiate/close (reuse `is_model_deployer` guard). Every transition writes `AUDIT.write(action='rfa.*')`; audit failure is fail-secure (mutation aborts).
- **Tests:** trigger-on-fraud, auto-examination transition + clock, show-cause milestone, close success, invalid transitions, window expiry, `is_rfa_triggered` query, route RBAC, show-cause deadline validation, close audit, FMR/CRILC integration.
- **Decision deferred to M3:** window-expiry **auto-close vs alert-only** — start **alert-only** (dashboard nudge on approaching due dates); auto-close considered only inside the L6.5 phase.
- **Alert-only:** the lifecycle *enforces a hearing* — `UNDER_EXAMINATION → CONFIRMED` is human-only and gated on a show-cause response; orthogonal to `AlertStatus` (no new alert enum).

**M2 outcome:** detection depth (risk index + standing-privilege + PAM content) and the audit spine (kill-switch + RFA lifecycle) land together — the bank gets richer signals and the governance controls that make them defensible, with alert-only preserved throughout.

---

## Milestone M3 — Full L6.5 Privileged-Action Interdiction Epic

The three L6.5 specs are **the same epic at two altitudes** (one architecture spec + two near-identical full build specs). They are merged into **one sequenced build** in four slices. Ship the standalone `/evaluate` + policies + pam-shim demo first (the quick win inside the epic), then the STEP_UP/HOLD console surfaces and hardening.

### M3.1 — Policy store + decision schema + evaluator (the PDP core) — *L6.5 policy before service*
- **Files create:** [services/action-gate/agsvc/__init__.py](services/action-gate/agsvc/__init__.py), [models.py](services/action-gate/agsvc/models.py), [policy_engine.py](services/action-gate/agsvc/policy_engine.py), [predicates.py](services/action-gate/agsvc/predicates.py), [governance_client.py](services/action-gate/agsvc/governance_client.py), [policies/policies.yaml](services/action-gate/agsvc/policies/policies.yaml)
- **Files edit:** [backend/rules_engine/rules/sod_matrix.yaml](backend/rules_engine/rules/sod_matrix.yaml) (add a single `[action_gate]` section — **no fork** of the toxic-combination matrix), [tests/conftest.py](tests/conftest.py) (append `ROOT/'services'/'action-gate'` to the service sys.path list at lines 13–25, alongside pam-shim/hitl-gate).
- **Symbols:** `ActionEvent` (actor/action.verb+channel/object/context.session_id/request_id/partner_id — **no `object.amount` in gating**), `ActionDecision` (full schema incl. `reason_codes[{source,code,detail-with-threshold+actual}]`, `challenge_id`, `hold_id`, `model_version`=policy fingerprint, `degraded`/`degraded_reason`), `PolicyConfig`, `ActionGate` (`load()/maybe_reload()/evaluate()/upsert_policy()/known_codes()` mirroring `RulesEngine`), predicates (`entitlement_self_grant`/`db_write_without_app_txn`/`maker_checker_same_actor` reuse; `swift_send_without_app_txn`/`bulk_export_high_volume` new — the latter consuming M2.3 PAM signals), `GovernanceClient` (5m TTL + `CircuitBreaker`).
- **Aggregation:** hard_gate OR SoD≥0.9 OR OPA deny → HOLD; soft over-threshold → STEP_UP; else ALLOW.
- **Tests:** per-predicate decision+detail; aggregation matrix; **OPA-vs-Python parity** (`SoDMatrix.score()` == `entitlement.rego` for conflict pairs); degradation fail-closed-for-privileged.
- **Alert-only:** `ActionEvent` schema *omits amount*; `ActionGate.evaluate()` has **no outbound calls** except read-only governance-DB + OPA.

### M3.2 — Gate service + idempotency + degradation (FastAPI :8096) — *needs M3.1*
- **Files create:** [services/action-gate/agsvc/main.py](services/action-gate/agsvc/main.py), [Dockerfile](services/action-gate/Dockerfile), [requirements.txt](services/action-gate/requirements.txt)
- **Endpoints:** `POST /api/v1/actions/evaluate` (sync, idempotent on `request_id` via `reliability.DEDUPE` 30s), `POST /api/v1/step-ups/{id}/challenge`, `GET /api/v1/step-ups/{id}`, `GET/POST /api/v1/holds/{id}`, `GET /health`, `GET /metrics` (Prometheus: `action_gate_decisions_total{decision}`, `_latency_seconds`, `_challenges_total`, `_holds_total`, `_degraded_total`).
- **Latency targets:** ALLOW p99 <10ms (in-proc, no I/O); STEP_UP ~50ms; HOLD ~100ms.
- **Tests:** idempotency (replayed request_id → identical decision, no double row); policy hot-reload (mtime fingerprint); degradation (governance down → privileged HOLD degraded, routine ALLOW; OPA timeout → Python fallback).
- **Alert-only:** service answers decisions only; **source system enforces** — no actuator. Network-egress policy in compose blocks any reach into CBS/PAM/IGA.

### M3.3 — Governance tables, queues, four-eyes integration & pam-shim e2e — *needs M3.2*
- **Files create:** [backend/services/api/app/routes/action_gate_routes.py](backend/services/api/app/routes/action_gate_routes.py), [tests/test_action_gate.py](tests/test_action_gate.py), [tests/integration/test_action_gate_e2e.py](tests/integration/test_action_gate_e2e.py)
- **Files edit:** [governance/db/models.py](governance/db/models.py), [governance/db/schema.sql](governance/db/schema.sql), [backend/services/api/app/routes/__init__.py](backend/services/api/app/routes/__init__.py), [deploy/compose/docker-compose.platform.yml](deploy/compose/docker-compose.platform.yml)
- **Governance tables (`Base` models, `CREATE TABLE IF NOT EXISTS`):** `StepUp` (status pending/mfa_passed/manager_approved/approved/denied), `Hold` (status pending_review/approved_via_four_eyes/rejected + proportionality/explanation/dpia_binding — verbatim hitl-gate semantics), `ActionDecisionEvent` (request_id UNIQUE, reason_codes JSON, policy_version, audit_id FK, degraded).
- **Console routes (clone of [rules_routes.py](backend/services/api/app/routes/rules_routes.py) + disposition patterns):** `GET /action-gate/policies`; `POST /action-gate/policies` + `POST /action-gate/policies/{change_id}/approve` (TUNE_RULES-style capability + `check_four_eyes`, proposer≠approver); `GET /action-gate/holds`; `POST /action-gate/holds/{id}/decision` (DISPOSITION capability + `check_disposition` no-self-review). Register router at `/action-gate` in `routes/__init__.py`.
- **Compose:** add `hawkeye-action-gate` (build `services/action-gate`, `8096:8096`, `/health` check, `GOVERNANCE_DB_URL`, policies-dir mount, `depends_on: [governance-api, pam-shim]` graceful) — mirror the existing pam-shim/hitl-gate stanzas.
- **E2E demo (the headline narrated path):** `pam-shim POST /sessions/{id}/command` for a `self_grant`/`drop_database` → action-gate `/evaluate` → `HOLD_FOR_REVIEW` → `Hold` row + hitl-gate DPIA classification → console `GET /action-gate/holds` → four-eyes approve → outcome `permitted_for_human_initiated_execution` (**assert NO auto-execution**). STEP_UP path: `entitlement_grant` soft → challenge → MFA/manager approve → retry with same `request_id` → ALLOW.
- **Tests:** four-eyes policy change (self-approval 403); SoD on HOLD decision (subject/originator cannot resolve); **alert-only invariant scan** (no endpoint accepts/gates `object.amount`; no endpoint emits a block command toward a source; every decision reversible/contestable); audit chain (evaluate→hold→approval = 3 hash-chained events linked by audit_id).
- **Alert-only:** every outcome reversible; HOLD inherits SBI v Rajesh Agarwal natural-justice binding (DPIA sign-off + contestable explanation + human hearing).

### M3.4 — Frontend surfaces (HOLD queue, step-up status, policy admin) — *needs M3.3*
- **Files edit:** [frontend/src](frontend/src) — HOLD review queue (actor PII-tokenized, verb/object, severity, reason_codes with threshold+actual, proportionality+explanation, DPIA binding) backed by `GET /action-gate/holds`; four-eyes decision panel (approve/reject + mandatory justification, DISPOSITION RBAC, no self-review — reuse disposition UI affordances); read-only STEP_UP status; Policy-admin screen (DGM Compliance) driving propose→second-approver, mirroring the rules-tuning screen.
- **Alert-only (explicit in UI):** every screen states outcomes are *alerts/holds for human action* and money is never auto-blocked.

**M3 outcome:** a complete, demo-real, audit-defensible L6.5 interdiction engine on the existing compose topology — source-enforced, reversible-by-construction, four-eyes-governed, with zero new external infra.

---

## Sequencing & Risk Summary

- **Ship order:** M1 (all five in parallel; M1.5 gates M2.1) → M2.2 → M2.1; M2.3, M2.4, M2.5 in parallel with the M2 detection items → M3.1 → M3.2 → M3.3 → M3.4.
- **Cross-milestone feeds:** M1.5 grievance → M2.1 risk index; M2.2 standing-privilege → M2.1 risk index; M2.3 PAM content → M3.1 `bulk_export_high_volume` predicate; M3.1 policy core → M3.2 service → M3.3 integration → M3.4 frontend.
- **Alert-only is enforced by tests, not just convention:** M3.3 includes a static scan asserting no action-gate endpoint touches `object.amount` or emits a block command.


---

## Appendix A — Dependency graph

- `M1.5 grievance feature -> M2.1 insider-risk index (risk index reads grievance_recency)`
- `M2.2 standing-privilege feature -> M2.1 insider-risk index (risk index reads standing_privilege)`
- `M2.3 PAM session-content -> M3.1 PDP core (bulk_export_high_volume predicate consumes PAM mass-select signals)`
- `M3.1 PDP core (policy store + evaluator) -> M3.2 gate service (service hosts ActionGate.evaluate)`
- `M3.2 gate service -> M3.3 governance tables + console routes + pam-shim e2e`
- `M3.3 integration (holds queue + policies routes) -> M3.4 frontend surfaces`
- `M1.1 SUSPENSE_NOSTRO_LAPPING rule -> M1.1 rfa.py _RFA_TRIGGER_CODES update (RFA tag depends on the new reason code)`
- `M1.4 ArtifactMeta.risk_tier -> M2.4 kill-switch (ArtifactMeta.disabled flag added on same registry surface; tier+disabled co-located)`
- `M2.5 RFA lifecycle trigger -> disposition_routes outcome=fraud path (trigger fires atomically before record_disposition)`
- `M3.1 sod_matrix.yaml [action_gate] section -> M3.1 OPA-vs-Python parity test (shared matrix must match entitlement.rego)`

## Appendix B — Risk register

1. Alert-only erosion in L6.5: a future dev could add object.amount gating or an auto-execute HOLD outcome. Mitigation: ActionEvent schema omits amount; M3.3 ships a static invariant scan asserting no endpoint reads object.amount or emits a block command; design docs state Hawk-Eye is policy-author/audit-sink only.
2. Insider-risk index composition weights (HR 30/access 35/anomaly 35) are stubs with no labeled ground truth; peer-fairness z-clamp can suppress alerts in fraud-concentrated cohorts. Mitigation: flag weights for calibration; mandate HITL review; do not auto-action on the score.
3. RFA lifecycle is XL and touches governance DB + disposition + FMR/CRILC; backward-compat risk with the legacy rfa.tag() boolean. Mitigation: keep should_tag_rfa/tag unchanged, add rfa_examinations as an orthogonal join; fail-secure on audit-write failure; start window-expiry as alert-only (auto-close deferred to L6.5).
4. Governance DB availability couples L6.5 decision latency. Mitigation: GovernanceClient CircuitBreaker + 5m TTL cache; fail-closed (HOLD) only for privileged, fail-open (ALLOW) for routine — privileged never silently allowed; ~100ms read timeout.
5. OPA runtime unavailable / parity drift between SoDMatrix and entitlement.rego. Mitigation: single shared [action_gate] section in sod_matrix.yaml (no fork); policy_timeout flag falls back to deterministic Python SoDMatrix.score(); a parity test asserts equality on all conflict pairs.
6. Kill-switch disabling all critical ML layers could collapse alert volume. Mitigation: L1 rules are never disableable so an alert always survives; fallback paths to remaining layers and to L1-only are tested; tier-1 disable should require CRO sign-off (governance policy pre-check).
7. PAM parser brittleness on non-standard SQL dialects/shell escaping and false-positive DDL chains from legitimate DBA migrations. Mitigation: verb-only partial-parse fallback + log unparseable commands; role!=dba filter on DDL anomaly; tunable thresholds; cache per session_id and batch-parse offline to bound online latency.
8. Idempotency dedup correctness across restarts / request_id TTL edges could create duplicate HOLD/StepUp rows. Mitigation: reliability.DEDUPE keyed on request_id (30s window matched to hitl-gate latency) + ActionDecisionEvent.request_id UNIQUE constraint; replay test asserts a single row.
9. Feature-name coupling: standing-privilege rule and risk index read features by exact column name; a rename in featurize.py silently zeroes them. Mitigation: strong naming convention + unit tests asserting feature presence in the featurize output.
10. Memory leak in AUDIT_CONFIG_TAMPERING per-entity counter if decay not honored. Mitigation: timestamp-keyed decay (default 24h) with a bounded entity map (<=100) per FeatureReader instance.
11. Compose/conftest wiring gaps for the new service: agsvc imports won't resolve in tests and the container won't be in the local stack. Mitigation: append ROOT/'services'/'action-gate' to the conftest sys.path list (lines 13-25) and register hawkeye-action-gate in docker-compose.platform.yml mirroring pam-shim/hitl-gate stanzas, with a /health check.
12. Four-eyes bypass on policy changes via role alias/session spoofing. Mitigation: check_four_eyes enforces proposer_id != approver_id at the JWT-bound Principal level; self-approval returns 403; mandatory change_reason audit field; tests confirm rejection.

## Appendix C — Open confirmations (non-blocking; defaults chosen, override at green-light)

- Grievance count scope: lifetime vs rolling 90/180-day window (spec assumes lifetime; affects M1.5 feature + any future grievance rule threshold).
- CFR category sourcing: confirm reason_codes->category mapping is consistent across FMR and CFR, else cfr_entry defaults to 'others' (M1.3).
- RFA window-expiry behavior at the 180d boundary: confirm alert-only (dashboard nudge) for now, with auto-close reserved for the L6.5 phase (M2.5).
- Tier-1 model disable approval: confirm whether CRO sign-off is enforced in code (disable_routes pre-check) or governance-policy-only; approval_by is currently an optional field (M2.4).
- Action-gate policy capability name: confirm reuse of TUNE_RULES vs a new TUNE_ACTIONS capability for the four-eyes policy-change flow (M3.3).
- SUSPENSE_NOSTRO_LAPPING verb taxonomy: confirm actual CBS/SWIFT/RTGS verbs (suspense_post/nostro_post/reconcile vs post_suspense_item/reconcile_suspense_item) so the YAML post_verbs/recon_verbs defaults match real events (M1.1).
- RFA + suspense exposure thresholds (RFA_EXPOSURE_INR ₹50L) flagged for legal/compliance review before any production posture (M1.1, M2.5).

## Appendix D — Explicitly OUT of scope this round (Extra / Skip)

- **FMR/CFR live submission to RBI** — generators done; submission is a bank-side ops bridge (mTLS + creds), stays SCAFFOLD.
- **Insider-enabled mule onboarding** — needs new CBS KYC + account-open feeds; drifts toward customer-fraud boundary.
- **Vernacular (Hindi/regional) narratives** — `ml/narrative/gateway.py` works English-only; adding a lang param is cheap but low audit value.
- **IS-audit evidence-pack PDF, SCBMF board pack** — reporting niceties; raw evidence already in WORM audit trail.
- **LoU/LC sanctioned-limit rule, cross-CBS ring detection, BC/AePS operator monitoring, dealer-blotter cancel-rebook feature** — valuable but feed-gated; build when the bank wires the feeds.
- **Officer-velocity fast-lane rule, insider-assisted-takeover rules, JIT/recertification** — Phase B follow-ons (best hosted on the risk index / after PAM content lands).

## Appendix E — L6.5 architecture (full decision record)

**Chosen:** L6.5 Privileged-Action Interdiction Engine as a synchronous Policy-Decision-Point microservice (services/action-gate/, port 8096) — a synthesis of Proposal 1 (clean standalone microservice + RulesEngine/HITL reuse + ALLOW/STEP_UP/HOLD vocabulary) with Proposal 3 grafted in as the enforcement model (source systems enforce LOCALLY; Hawk-Eye is policy-author + audit-sink and never reaches into CBS/PAM/IGA), OPA entitlement.rego reuse, idempotent request_id dedup, and fail-closed-for-privileged degradation. Reject the inline-pipeline approach (Proposal 2) — it conflates a pre-action gate with the post-event alert path.

The decision vocabulary is ALLOW | STEP_UP | HOLD_FOR_REVIEW (Proposal 1's words, kept over Proposal 3's bare DENY, because DENY reads like a hard block which is exactly what the bank's lawyers must not see — STEP_UP/HOLD are demonstrably reversible). The gate ONLY governs reversible STAFF actions (entitlement self-grant, SWIFT/SO message send, bulk export, direct DB write, same-actor maker+checker, toxic-combination entitlement exercise) — NEVER money movement. The PDP returns a decision + deniable reason codes; the calling SCAFFOLD source system (pam-shim today; CyberArk/CBS/IGA in prod) enforces it locally. HOLD routes to the existing hitl-gate four-eyes/DPIA-bound queue; STEP_UP issues an MFA/manager challenge; ALLOW is logged. Policy store is hot-reloadable YAML mirroring rules.yaml, edited only through the existing four-eyes change-controlled flow.

**Rationale:** This is the best fit for THIS repo on every optimization axis. (1) Alert-only safety: the gate's enforcement lives in the SOURCE system, not in Hawk-Eye — Hawk-Eye authors policy and sinks audit but never executes a block, which is the exact posture the existing pam-shim already implements (POST /sessions/{id}/command returns 403 LOCALLY for least-privilege). STEP_UP/HOLD are reversible by construction; no money path is ever touched. (2) Reuse of existing patterns: RulesEngine gives hot-reload + predicate registry + known_codes() guard + SoDMatrix.score() + the OPA entitlement.rego bundle already kept "in lockstep"; hitl-gate gives the DPIA-bound, proportionality+explanation, pending_review four-eyes queue verbatim; rules_routes gives the propose->second-approver->persist change-control for the policy store; reliability.CircuitBreaker and reliability.DEDUPE give degradation + idempotency primitives; audit AUDIT.write gives hash-chained WORM logging. (3) Demo-ability: pam-shim's existing /sessions/{id}/command becomes the live caller — a self-grant or drop_database command flows pam-shim -> action-gate /evaluate -> STEP_UP/HOLD -> hitl-gate queue -> human approve, all on the existing compose topology, a complete narrated demo with zero new external infra. (4) Realistic SCAFFOLD integration: source systems are external SCAFFOLD per the golden rules; a PDP that they call (rather than an inline hook inside Hawk-Eye's own pipeline) is exactly how CyberArk/BeyondTrust/Finacle integrate in reality. (5) Audit defensibility: every decision writes a hash-chained audit event with deniable reason codes; policy edits are four-eyes + versioned; HOLD inherits the SBI v Rajesh Agarwal natural-justice binding (DPIA sign-off, contestable explanation, human hearing before any classification). A separate service keeps L6.5 latency and availability decoupled from the alert pipeline's SLA.

**Why not the alternatives:** Proposal 2 (INLINE gate in OnlinePipeline) is architecturally backwards and was rejected: the online pipeline runs AFTER an event has already occurred and emits an alert — it cannot gate an action BEFORE it proceeds, which is the entire point of interdiction. Embedding ALLOW/STEP_UP/HOLD as alert metadata means the privileged action has already happened by the time the decision is computed, so the "gate" gates nothing; it only annotates. It also pollutes the alert-only invariant by overloading AlertStatus with action-execution states (ACTION_PENDING_APPROVAL signalling the data layer to execute) and couples gate latency/failures into the alert hot path. Its only good idea — explainable reason codes with threshold+actual-value detail — is grafted into the chosen design's reason_codes. Proposal 3 (pure PDP) has the right enforcement model (source enforces, Hawk-Eye is policy-author/audit-sink, OPA reuse, idempotency, fail-open-routine/fail-closed-privileged) but is weaker as a standalone deliverable: it scatters code into backend/pdp + backend/routes (a non-existent dir; routes live under backend/services/api/app/routes), bakes enforcement into a bare ALLOW/DENY/STEP_UP that reads as a hard block, and underuses the hitl-gate four-eyes HOLD queue (it just emits an alert on DENY). I took its enforcement philosophy, OPA bundle reuse, request_id dedup, and degradation policy and merged them into Proposal 1's cleaner microservice skeleton. Proposal 1 alone scored well but treated the source-system call as abstract; grounding it on the real pam-shim caller and Proposal 3's source-enforces invariant makes it demo-real and audit-defensible.

**Decision schema:** ActionDecision = {action_id: str, request_id: str (idempotency key, caller-generated uuid4), decision: ALLOW | STEP_UP | HOLD_FOR_REVIEW, severity: low|medium|high, reason_codes: [{source: rule|sod|opa|gate, code: str, detail: str including threshold and actual value}], challenge_id: str|null (STEP_UP only), challenge_type: mfa|manager_approval (STEP_UP), hold_id: str|null (HOLD only), hold_poll_url: str|null, model_version: str (policy fingerprint version), evaluated_at: ISO8601-Z, audit_id: str, degraded: bool, degraded_reason: str|null}. Aggregation: if ANY hard_gate policy or SoD>=0.9 or OPA deny -> HOLD_FOR_REVIEW; else if ANY soft policy over threshold -> STEP_UP; else ALLOW. StepUp.status in [pending, mfa_passed, manager_approved, approved, denied]. Hold.status in [pending_review, approved_via_four_eyes, rejected] (verbatim hitl-gate semantics). NO decision value blocks money; ALLOW/STEP_UP/HOLD all leave the action contestable and reversible.

**Data flow:** 1. A privileged STAFF action originates in a SCAFFOLD source system — today the pam-shim /sessions/{id}/command (prod swap: CyberArk/BeyondTrust pre-session, CBS pre-SO-send, IGA pre-grant). 2. The source system POSTs /api/v1/actions/evaluate with an ActionEvent {actor, action.verb/channel, object, context.session_id, request_id, partner_id}. 3. action-gate dedups on request_id (reliability.DEDUPE, 30s window), then ActionGate.evaluate(): reads online features (entitlement_self_grant, db_write_without_app_txn, bulk_export, swift_without_cbs_match, maker_checker_same_actor), runs the shared predicate registry + SoDMatrix.score() + OPA entitlement.rego outcomes (toxic_combinations/self_grant/maker_checker_same), and consults governance_client for live SoD/DPIA state. 4. Aggregates to ALLOW | STEP_UP | HOLD_FOR_REVIEW with reason_codes; AUDIT.write logs the decision (hash-chained WORM). 5. Returns the decision. The SOURCE SYSTEM enforces locally: ALLOW -> proceed; STEP_UP -> source initiates MFA/manager challenge via /step-ups/{id}/challenge, polls until approved/denied; HOLD_FOR_REVIEW -> a hold row + a hitl-gate classification (DPIA-bound) are created and the source pauses the action, polling /holds/{id}. 6. A human resolves the HOLD through the four-eyes /action-gate/holds/{id}/decision (RBAC + SoD, no self-review); on approve, the OUTCOME is "action permitted for human-initiated execution" — never an auto-execute. 7. Policy changes flow propose -> second-approver (DGM Compliance) -> upsert_policy -> hot-reload, identical to rules_routes, every edit audited. Hawk-Eye NEVER reaches outward into CBS/PAM/IGA to block; it only answers decisions and records audit.

**Alert-only argument:** The golden rule is preserved on three independent grounds. (1) Scope: the gate governs ONLY reversible STAFF actions (entitlement self-grant, message send, bulk export, direct DB write, same-actor maker+checker) — it has no money-movement code path at all (ActionEvent deliberately omits object.amount from gating logic), so it can never block, hold, or delay a payment. (2) Enforcement locus (grafted from Proposal 3): Hawk-Eye is the policy AUTHOR and audit SINK; the SCAFFOLD source system enforces the decision in its own boundary, exactly as the existing pam-shim already returns 403 locally for least-privilege. Hawk-Eye issues no outbound command to CBS/PAM/IGA — it cannot auto-block anything because it has no actuator. (3) Reversibility + natural justice: STEP_UP and HOLD_FOR_REVIEW are by construction undoable — STEP_UP lets the actor re-attempt after MFA/manager sign-off; HOLD routes to the DPIA-bound hitl-gate four-eyes queue where a human, after a contestable proportionality+explanation review (SBI v Rajesh Agarwal hearing), may approve and let the action proceed. No classification of a person and no permanent block ever occurs without a human decision. Even an approved HOLD only marks the action as "permitted for human-initiated execution"; nothing auto-executes and nothing auto-punishes. The alert-only invariant (emit signals for humans; never auto-block money; classify only after a hearing) holds end-to-end.

**Latency / fallback:** Targets: ALLOW p99 <10ms (in-process predicate + cached SoD eval, no I/O), STEP_UP ~50ms (challenge issue), HOLD ~100ms (governance write + hitl-gate enqueue). The /evaluate call is synchronous; STEP_UP challenge and HOLD review are async-pollable. Degradation policy (merged from Proposal 3): governance_client wraps reads in reliability.CircuitBreaker — after 3 consecutive failures it opens and the gate FAILS CLOSED for privileged verbs (returns HOLD_FOR_REVIEW with degraded=true, degraded_reason="governance_unavailable", queued for re-check on recovery) and fails OPEN (ALLOW) only for routine/non-privileged verbs; it NEVER silently degrades a privileged action to ALLOW. OPA-eval timeout falls back to the deterministic Python rules_engine path (policy_timeout flag). request_id idempotency window 30s. If the whole action-gate service is down, the source system applies ITS configured fallback (privileged -> deny/queue, routine -> allow) — degradation config lives upstream in the SCAFFOLD system, not in Hawk-Eye, preserving the never-reach-in principle. Prometheus /metrics: action_gate_decisions_total{decision}, action_gate_latency_seconds, action_gate_challenges_total, action_gate_holds_total, action_gate_degraded_total — extending the existing prometheus_client pattern from hitl-gate/pam-shim.

**Frontend surface:** Investigator/approver console (frontend/src, React/TS) surfaces three things. (1) A HOLD review queue analogous to the existing alert/disposition triage, backed by GET /action-gate/holds: each row shows actor (PII-tokenized), action verb/object, severity, the deniable reason_codes with threshold+actual values, the proportionality + explanation text (so the decision is contestable), and the DPIA binding. (2) A four-eyes decision panel: approve/reject with mandatory justification, RBAC-gated (DISPOSITION capability; escalation/override reserved for AGM Vigilance), with SoD preventing self-review — reusing the disposition UI affordances. (3) For STEP_UP, the actor-facing source system shows an MFA/manager-approval modal and a hold timer/poll state; the console shows a read-only step-up status. A Policy admin screen (DGM Compliance) lists action-gate policies and drives the propose -> second-approver four-eyes change flow, mirroring the existing rules-tuning screen. Every screen makes explicit that outcomes are alerts/holds for human action and that money is never auto-blocked.
