-- =============================================================================
-- Hawk-Eye ClickHouse — investigative search helpers (DATABASE-4)
-- Blueprint: Part 8 (inverted-index log search; sub-second queries, l.305-306).
-- -----------------------------------------------------------------------------
-- Parameterized VIEWS the investigation API (BACKEND) calls. ClickHouse
-- parameterized views are invoked with FUNCTION-CALL syntax (named args), NOT
-- the `--param_*` query-substitution mechanism:
--   SELECT * FROM hawkeye.search_events_by_employee(employee='EMP-7f3a', limit=50)
--   SELECT * FROM hawkeye.search_alerts_fulltext(token='beneficiary', limit=50)
-- (verified live on ClickHouse 25.3; `--param_x` is for parameterized QUERIES,
-- not views.)
--
-- The free-text views search lower(payload)/lower(reason_text) so they are
-- CASE-INSENSITIVE *and* engage the tokenbf indices built on the SAME lower()
-- expression (idx_payload_tokens / idx_reason_tokens) — EXPLAIN indexes=1 shows
-- granule pruning. Also exercise the skip indices (idx_evt_*, idx_alert_*) and
-- the full-text indices (idx_payload_ft, idx_reason_ft) for sub-second search.
-- =============================================================================

-- ---- search by employee (entity-360 event stream) ---------------------------
CREATE VIEW IF NOT EXISTS hawkeye.search_events_by_employee AS
SELECT
    event_id, ts, action_verb, action_channel, action_maker_checker,
    object_beneficiary_id, object_account_id, object_amount, object_currency,
    context_src_ip, context_device, context_session_id, context_is_off_hours
FROM hawkeye.events
WHERE actor_employee_id = {employee:String}
ORDER BY ts DESC
LIMIT {limit:UInt32};

-- ---- search by IP (who used this source IP) ---------------------------------
CREATE VIEW IF NOT EXISTS hawkeye.search_events_by_ip AS
SELECT event_id, ts, actor_employee_id, action_verb, context_device, context_session_id
FROM hawkeye.events
WHERE context_src_ip = {ip:String}
ORDER BY ts DESC
LIMIT {limit:UInt32};

-- ---- search by device (shared-device / lateral-movement investigation) ------
CREATE VIEW IF NOT EXISTS hawkeye.search_events_by_device AS
SELECT event_id, ts, actor_employee_id, context_src_ip, action_verb, context_session_id
FROM hawkeye.events
WHERE context_device = {device:String}
ORDER BY ts DESC
LIMIT {limit:UInt32};

-- ---- search by beneficiary (who paid / created this payee) -------------------
CREATE VIEW IF NOT EXISTS hawkeye.search_events_by_beneficiary AS
SELECT event_id, ts, actor_employee_id, action_verb, object_account_id, object_amount
FROM hawkeye.events
WHERE object_beneficiary_id = {beneficiary:String}
ORDER BY ts DESC
LIMIT {limit:UInt32};

-- ---- free-text search over the event payload (inverted index) ---------------
-- hasToken() / multiSearchAny() over the full-text-indexed payload column.
CREATE VIEW IF NOT EXISTS hawkeye.search_events_fulltext AS
SELECT event_id, ts, actor_employee_id, action_verb, payload
FROM hawkeye.events
WHERE hasToken(lower(payload), lower({token:String}))
ORDER BY ts DESC
LIMIT {limit:UInt32};

-- ---- free-text search over alert reason codes (inverted index) --------------
CREATE VIEW IF NOT EXISTS hawkeye.search_alerts_fulltext AS
SELECT alert_id, entity_id, created_ts, risk_score, severity, status, reason_text
FROM hawkeye.alerts
WHERE hasToken(lower(reason_text), lower({token:String}))
ORDER BY created_ts DESC
LIMIT {limit:UInt32};

-- ---- alerts for an entity (case workflow join key) --------------------------
CREATE VIEW IF NOT EXISTS hawkeye.search_alerts_by_entity AS
SELECT alert_id, created_ts, risk_score, severity, confidence, status, exposure_inr, sla_due_ts
FROM hawkeye.alerts
WHERE entity_id = {entity:String}
ORDER BY created_ts DESC
LIMIT {limit:UInt32};

-- ---- entity-360 unified timeline (events + alerts + dispositions) -----------
-- One ranked timeline for an entity: each row tagged with its kind. Drives the
-- investigator entity-360 / timeline view (BACKEND `/entities/{id}/timeline`).
CREATE VIEW IF NOT EXISTS hawkeye.entity_360_timeline AS
SELECT
    'event' AS kind, ts AS at, event_id AS ref,
    concat(action_verb, ' / ', coalesce(object_beneficiary_id, '')) AS detail
FROM hawkeye.events
WHERE actor_employee_id = {entity:String}
UNION ALL
SELECT
    'alert' AS kind, created_ts AS at, alert_id AS ref,
    concat('risk=', toString(risk_score), ' ', reason_text) AS detail
FROM hawkeye.alerts
WHERE entity_id = {entity:String}
UNION ALL
SELECT
    'disposition' AS kind, ts AS at, alert_id AS ref,
    concat(toString(outcome), ' by ', disposed_by) AS detail
FROM hawkeye.dispositions
WHERE entity_id = {entity:String}
ORDER BY at DESC
LIMIT {limit:UInt32};
