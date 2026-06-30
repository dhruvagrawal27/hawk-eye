-- =============================================================================
-- Hawk-Eye ClickHouse — `events` (DATABASE-3)
-- Mirrors the L0 Unified Event contract (BACKEND.md §1, blueprint Part 5.1):
--   field groups Actor / Action / Object / Context / Linkage.
-- TODO reconcile with data/schemas/l0_event (.avsc/.proto) once DATA finalizes
--   (currently field-for-field identical to BACKEND.md §1 / data.schemas.l0_event).
-- Blueprint: Part 8 (l.305, 317-318), Part 9.2 (compression ~10-20x, l.357),
--            Part 5.1 (event field groups).
-- -----------------------------------------------------------------------------
-- Engine: ReplacingMergeTree(ingested_at) → idempotent on event_id (dedupes a
--   replay; BACKEND keys exactly-once on a deterministic event_id, §6b). The
--   apply script rewrites this to ReplicatedReplacingMergeTree for the cluster.
-- Partition: toYYYYMM(ts). Order: (actor_employee_id, ts, event_id).
-- Tiering: hot SSD (default) -> cold object-store (30d) -> archive (365d) via the
--   `tiered` storage policy (storage_configuration.xml) + TTL ... TO VOLUME.
-- Compression: ZSTD on wide/text columns, Delta+ZSTD on timestamps.
-- =============================================================================
CREATE TABLE IF NOT EXISTS hawkeye.events
(
    -- identity + time --------------------------------------------------------
    event_id              String,
    ts                    DateTime64(3, 'UTC') CODEC(Delta, ZSTD(3)),

    -- Actor group (BACKEND.md §1 actor.*) ------------------------------------
    actor_employee_id     String,
    actor_role            LowCardinality(String),
    actor_dept            LowCardinality(String),
    actor_branch          LowCardinality(String),
    actor_tenure_days     Nullable(Int32),
    actor_peer_group      LowCardinality(String),
    actor_privileged_flag UInt8 DEFAULT 0,
    actor_leaver_flag     UInt8 DEFAULT 0,

    -- Action group (BACKEND.md §1 action.*) ----------------------------------
    action_verb           LowCardinality(String),
    action_channel        LowCardinality(String),
    action_maker_checker  LowCardinality(String),

    -- Object group (BACKEND.md §1 object.*) ----------------------------------
    object_beneficiary_id Nullable(String),
    object_account_id     Nullable(String),
    object_amount         Nullable(Int64),                       -- integer INR (CONTEXT.md §6)
    object_currency       LowCardinality(String) DEFAULT 'INR',

    -- Context group (BACKEND.md §1 context.*) --------------------------------
    context_src_ip        String,
    context_device        LowCardinality(String),
    context_geo           LowCardinality(String),
    context_session_id    String,
    context_layer         LowCardinality(String),
    context_is_off_hours  UInt8 DEFAULT 0,

    -- Linkage group (BACKEND.md §1 linkage.* — correlation keys) -------------
    linkage_swift_ref           Nullable(String),
    linkage_cbs_txn_id          Nullable(String),
    linkage_app_txn_id          Nullable(String),
    linkage_db_write_id         Nullable(String),
    linkage_related_event_id    Nullable(String),
    linkage_customer_account_id Nullable(String),
    linkage_extra               Map(String, String),             -- additive (extra=allow)

    -- full-text search payload (DATABASE-4 inverted index target) ------------
    payload               String CODEC(ZSTD(3)),                 -- canonical event JSON

    -- governance / bookkeeping ----------------------------------------------
    pii_tokenized         UInt8 DEFAULT 1,                       -- raw PII never lands here
    ingested_at           DateTime64(3, 'UTC') DEFAULT now64(3) CODEC(Delta, ZSTD(3))
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (actor_employee_id, ts, event_id)
TTL toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
