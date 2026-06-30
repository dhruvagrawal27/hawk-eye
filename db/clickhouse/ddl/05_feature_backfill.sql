-- =============================================================================
-- Hawk-Eye ClickHouse — `feature_backfill` (DATABASE-3)
-- The OFFLINE feature store target. Definitions are IDENTICAL to the online
--   Feast/Redis features (DATA owns the defs; one definition serves train+serve →
--   no train/serve skew, Part 21.5 l.825 / Part 6). DATABASE provides the
--   skew-free offline sink; DATA writes the rows.
-- Key convention: feature_key = "<entity>:<feature>:<window>" (DATA config.py;
--   CONTEXT.md feature-key naming).
-- Lineage: feature_set_version ties a backfill row to the feature-set version a
--   model was trained on (Part 21.5 dataset-hash + feature-set-version lineage).
-- Point-in-time: event_ts is the as-of time → correct temporal joins (no leakage).
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.feature_backfill
(
    entity_id           String,
    feature_name        LowCardinality(String),
    window              LowCardinality(String),                -- e.g. '30d', 'all'
    feature_key         String,                                -- "<entity>:<feature>:<window>"
    value_num           Nullable(Float64),                     -- numeric features
    value_str           Nullable(String),                      -- categorical/string features
    event_ts            DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),  -- point-in-time (as-of)
    feature_set_version String,                                -- lineage (Part 21.5)
    created_ts          DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(created_ts)
PARTITION BY toYYYYMM(event_ts)
ORDER BY (entity_id, feature_name, window, event_ts)
TTL toDateTime(event_ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(event_ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
