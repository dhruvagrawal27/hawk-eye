-- =============================================================================
-- Hawk-Eye ClickHouse — `dispositions` (DATABASE-3)
-- Mirrors the EDD disposition contract (BACKEND.md §5): the human outcome is the
--   classification (ALERT-ONLY). Each disposition writes a LABEL row that ML's
--   feedback loop reads (DATA label-source-4) and carries the `audit_id` that
--   ties it to the WORM trail (DATABASE-6).
-- Blueprint: Part 8, Part 9.3 (dispositions to append-only/WORM), Part 10 (feedback).
-- Fraud carve-out: outcome='fraud' rows are held longer by retention (DATABASE-9).
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.dispositions
(
    alert_id        String,
    entity_id       String,
    outcome         Enum8('fraud' = 1, 'false_positive' = 2, 'inconclusive' = 3),  -- BACKEND.md §5
    resulting_status LowCardinality(String),                   -- confirmed_fraud|false_positive|inconclusive
    notes           String CODEC(ZSTD(3)),
    evidence_ids    Array(String),                             -- e.g. ['evt_8f2a1c90']
    label_written   UInt8 DEFAULT 0,                           -- §5 label_written
    feedback_queued UInt8 DEFAULT 0,                           -- §5 feedback_queued_for_retraining
    audit_id        String,                                    -- §5 audit_id (aud_*) → WORM
    disposed_by     String,                                    -- actor who dispositioned
    ts              DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),
    ingested_at     DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (alert_id, ts)
TTL toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
