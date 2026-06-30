-- =============================================================================
-- Hawk-Eye ClickHouse — `report_outputs` (DATABASE-3, Reporting seam)
-- SEAM (CONTEXT.md / prompt §5): BACKEND GENERATES regulatory reports
--   (FMR/CRILC/EWS/RFA/CFR/KRI); FRONTEND exports the UI; DATABASE STORES the
--   report OUTPUTS (object store) + their METADATA + retention class here.
-- We do NOT generate reports — we store their outputs + lineage + retention tag.
-- Blueprint: Part 16 (regulatory reporting), Part 28.2 (classification→retention).
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.report_outputs
(
    report_id        String,
    report_type      Enum8('fmr' = 1, 'crilc' = 2, 'ews' = 3, 'rfa' = 4, 'cfr' = 5, 'kri' = 6),
    period_start     Date,
    period_end       Date,
    object_uri       String,                                   -- s3://datasets/... or audit-archive
    content_hash     String,                                   -- sha256 of the report bytes
    retention_class  LowCardinality(String) DEFAULT 'regulatory',  -- drives DATABASE-9 windows
    generated_by     String,                                   -- actor / service (audited separately)
    generated_ts     DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),
    ingested_at      DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(generated_ts)
ORDER BY (report_type, generated_ts, report_id)
TTL toDateTime(generated_ts) + INTERVAL 90 DAY TO VOLUME 'cold',
    toDateTime(generated_ts) + INTERVAL 730 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
