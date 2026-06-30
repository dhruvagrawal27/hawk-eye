-- =============================================================================
-- Hawk-Eye ClickHouse — inverted (full-text) + skip indices (DATABASE-4)
-- Blueprint: Part 8 ("Search -> ClickHouse inverted indices", l.305-306, 318).
-- -----------------------------------------------------------------------------
-- Two families:
--   1. FULL-TEXT (inverted) on free-text payload columns → token/phrase search for
--      the investigation API (search free text over event payload / alert reasons).
--      ClickHouse 25.x: index TYPE `full_text` (renamed from `inverted`), behind
--      `allow_experimental_full_text_index = 1`. apply_ddl.sh sets that session
--      flag (and the legacy `allow_experimental_inverted_index` for <24.x).
--   2. SKIP indices (bloom_filter / tokenbf_v1 / ngrambf_v1 / minmax / set) on
--      high-cardinality investigative columns (employee, ip, device, session,
--      beneficiary, account, model_version, status) → granule pruning, sub-second.
--
-- NOTE: ADD INDEX only registers the index; existing parts are indexed by
-- MATERIALIZE INDEX (apply_ddl.sh runs it). New inserts are indexed automatically.
-- =============================================================================

-- ---- events: full-text over payload + skip indices on investigative cols ----
-- The `hasToken`-backing indices are on lower(payload) so the case-insensitive
-- search view (hasToken(lower(payload), lower(token))) actually engages them —
-- a skip/full-text index is only used when the predicate references the EXACT
-- indexed expression, so the index expression must match the query's lower(payload).
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_payload_ft payload TYPE full_text GRANULARITY 1;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_payload_tokens lower(payload) TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 1;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_payload_ngram lower(payload) TYPE ngrambf_v1(3, 4096, 3, 0) GRANULARITY 1;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_employee actor_employee_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_ip context_src_ip TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_device context_device TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_session context_session_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_beneficiary object_beneficiary_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_account object_account_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_amount object_amount TYPE minmax GRANULARITY 1;
ALTER TABLE hawkeye.events ADD INDEX IF NOT EXISTS idx_evt_verb action_verb TYPE set(0) GRANULARITY 1;

-- ---- alerts: full-text over reason_text + skip indices ----------------------
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_reason_ft reason_text TYPE full_text GRANULARITY 1;
-- on lower(reason_text) to match the case-insensitive search_alerts_fulltext view.
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_reason_tokens lower(reason_text) TYPE tokenbf_v1(8192, 3, 0) GRANULARITY 1;
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_alert_entity entity_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_alert_status status TYPE set(0) GRANULARITY 1;
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_alert_severity severity TYPE set(0) GRANULARITY 1;
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_alert_risk risk_score TYPE minmax GRANULARITY 1;
ALTER TABLE hawkeye.alerts ADD INDEX IF NOT EXISTS idx_alert_exposure exposure_inr TYPE minmax GRANULARITY 1;

-- ---- scores: model_version + layer pruning ----------------------------------
ALTER TABLE hawkeye.scores ADD INDEX IF NOT EXISTS idx_score_model model_version TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.scores ADD INDEX IF NOT EXISTS idx_score_layer layer TYPE set(0) GRANULARITY 1;
ALTER TABLE hawkeye.scores ADD INDEX IF NOT EXISTS idx_score_alert alert_id TYPE bloom_filter(0.01) GRANULARITY 4;

-- ---- dispositions: outcome + audit linkage + free-text notes ----------------
ALTER TABLE hawkeye.dispositions ADD INDEX IF NOT EXISTS idx_disp_outcome outcome TYPE set(0) GRANULARITY 1;
ALTER TABLE hawkeye.dispositions ADD INDEX IF NOT EXISTS idx_disp_audit audit_id TYPE bloom_filter(0.01) GRANULARITY 4;
ALTER TABLE hawkeye.dispositions ADD INDEX IF NOT EXISTS idx_disp_notes_ft notes TYPE full_text GRANULARITY 1;

-- ---- feature_backfill: fast feature lookup ----------------------------------
ALTER TABLE hawkeye.feature_backfill ADD INDEX IF NOT EXISTS idx_fb_feature feature_name TYPE set(0) GRANULARITY 1;
ALTER TABLE hawkeye.feature_backfill ADD INDEX IF NOT EXISTS idx_fb_key feature_key TYPE bloom_filter(0.01) GRANULARITY 4;
