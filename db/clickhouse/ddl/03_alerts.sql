-- =============================================================================
-- Hawk-Eye ClickHouse — `alerts` (DATABASE-3)
-- Mirrors the L6 Alert contract (BACKEND.md §2) column-for-column:
--   alert_id, entity_id, risk_score, severity, confidence, status, created_ts,
--   contributing_layers[], reason_codes[nested], exposure_inr, sla_due_ts,
--   pii_tokenized.
-- Blueprint: Part 8, Part 9.2, Part 9.3 (alerts to append-only/WORM via DATABASE-6).
-- ALERT-ONLY: an alert is a scored+explained request for a human; never an action.
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.alerts
(
    alert_id            String,
    entity_id           String,                                 -- = employee_id
    risk_score          UInt8,                                  -- 0..100 int (BACKEND.md §2)
    severity            Enum8('low' = 1, 'medium' = 2, 'high' = 3),
    confidence          Float32,                                -- 0..1
    status              Enum8(
        'open' = 1, 'assigned' = 2, 'in_review' = 3, 'block_requested' = 4,
        'confirmed_fraud' = 5, 'false_positive' = 6, 'inconclusive' = 7, 'closed' = 8
    ),
    created_ts          DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),
    contributing_layers Array(LowCardinality(String)),          -- e.g. ['L1_rules','L3_gbdt']

    -- reason_codes[] (BACKEND.md §2): heterogeneous (rule|shap|graph|sequence).
    -- Modeled as a Nested column; empty fields where a source does not use them.
    reason_codes Nested(
        source       LowCardinality(String),                   -- rule|shap|graph|sequence
        code         String,                                   -- rule code
        feature      String,                                   -- shap feature
        detail       String,                                   -- human detail
        contribution Float32                                   -- shap contribution
    ),

    exposure_inr        Int64,                                  -- integer INR
    sla_due_ts          DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),  -- created + RBI <=30d
    pii_tokenized       UInt8 DEFAULT 1,                        -- always 1 on egress (§2)

    -- search aids (DATABASE-4) ----------------------------------------------
    reason_text         String CODEC(ZSTD(3)),                  -- flattened reason_codes for full-text
    payload             String CODEC(ZSTD(3)),                  -- canonical alert JSON
    ingested_at         DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(created_ts)
ORDER BY (entity_id, created_ts, alert_id)
TTL toDateTime(created_ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(created_ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
