-- =============================================================================
-- Hawk-Eye ClickHouse — retention TTL-MOVE hot->cold->archive (DATABASE-9)
-- Blueprint: Part 28.2 (tiered hot->cold->archive, l.1208); Part 9.3 (RBI
--            record-keeping); Part 23.3 (lifecycle).
-- -----------------------------------------------------------------------------
-- The base DDL (db/clickhouse/ddl/*.sql) already declares the hot->cold->archive
-- TTL-MOVE. This file is the AUTHORITATIVE retention TTL (idempotent ALTERs) the
-- retention job applies, so the windows live in ONE place and match policies.yaml.
-- `MODIFY TTL` rewrites the move schedule; `materialize_ttl_after_modify=1` (the
-- default) re-evaluates existing parts.
--
-- Windows mirror db/retention/policies.yaml. Operational tables also EXPIRE old
-- partitions (DELETE) after the archive window; evidence tables (alerts,
-- dispositions, report_outputs) do NOT auto-expire (regulator-grade hold).
-- =============================================================================

-- events: sensitive — move hot->cold(30d)->archive(365d), expire at 1825d (5y)
ALTER TABLE hawkeye.events MODIFY TTL
    toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive',
    toDateTime(ts) + INTERVAL 1825 DAY DELETE;

-- scores: operational — same tiering, expire at 1825d
ALTER TABLE hawkeye.scores MODIFY TTL
    toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive',
    toDateTime(ts) + INTERVAL 1825 DAY DELETE;

-- alerts: sensitive/evidence — tier to archive at 365d; NO auto-expire (8y+ hold)
ALTER TABLE hawkeye.alerts MODIFY TTL
    toDateTime(created_ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(created_ts) + INTERVAL 365 DAY TO VOLUME 'archive';

-- dispositions: sensitive/evidence — tier to archive; NO auto-expire (fraud carve-out)
ALTER TABLE hawkeye.dispositions MODIFY TTL
    toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive';

-- feature_backfill: operational — shorter; expire at 1095d (3y)
ALTER TABLE hawkeye.feature_backfill MODIFY TTL
    toDateTime(event_ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(event_ts) + INTERVAL 180 DAY TO VOLUME 'archive',
    toDateTime(event_ts) + INTERVAL 1095 DAY DELETE;

-- report_outputs: regulatory — tier slower; NO auto-expire (10y hold)
ALTER TABLE hawkeye.report_outputs MODIFY TTL
    toDateTime(generated_ts) + INTERVAL 90 DAY TO VOLUME 'cold',
    toDateTime(generated_ts) + INTERVAL 730 DAY TO VOLUME 'archive';
