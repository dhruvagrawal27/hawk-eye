-- =============================================================================
-- Hawk-Eye ClickHouse — `scores` (DATABASE-3)
-- Per-layer (L1..L6) + fused score history. `model_version` is recorded on
--   EVERY score (Part 23.4 l.867-868; BACKEND.md §6a "model_version recorded on
--   every score") — reproducibility + audit + natural-justice.
-- Blueprint: Part 8, Part 9.2, Part 23.4.
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.scores
(
    event_id         String,                                    -- L0 event scored
    alert_id         Nullable(String),                          -- set once fused into an alert
    entity_id        String,                                    -- = employee_id
    layer            Enum8('L1' = 1, 'L2' = 2, 'L3' = 3, 'L4' = 4, 'L5' = 5, 'L6' = 6),
    raw_score        Float64,                                   -- per-layer 0..1 (pre-calibration)
    calibrated_score Float64,                                   -- calibrated 0..1 (L6 → 0..100 in alerts)
    model_version    String,                                    -- e.g. L3/lightgbm_gbdt/v1.4.2
    degraded         UInt8 DEFAULT 0,                           -- layer degraded at score time (§6a)
    ts               DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),
    ingested_at      DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (entity_id, ts, event_id, layer, model_version)
TTL toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
