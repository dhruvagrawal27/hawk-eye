-- =============================================================================
-- Hawk-Eye ClickHouse — materialize skip/full-text indices over EXISTING parts
-- (DATABASE-4). ADD INDEX only indexes NEW inserts; run this once to index data
-- already present. New inserts are indexed automatically thereafter.
-- =============================================================================
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_payload_ft;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_payload_tokens;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_payload_ngram;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_employee;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_ip;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_device;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_session;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_beneficiary;
ALTER TABLE hawkeye.events MATERIALIZE INDEX idx_evt_account;
ALTER TABLE hawkeye.alerts MATERIALIZE INDEX idx_reason_ft;
ALTER TABLE hawkeye.alerts MATERIALIZE INDEX idx_reason_tokens;
ALTER TABLE hawkeye.alerts MATERIALIZE INDEX idx_alert_entity;
ALTER TABLE hawkeye.scores MATERIALIZE INDEX idx_score_model;
ALTER TABLE hawkeye.dispositions MATERIALIZE INDEX idx_disp_notes_ft;
