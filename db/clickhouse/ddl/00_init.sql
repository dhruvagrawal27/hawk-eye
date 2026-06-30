-- =============================================================================
-- Hawk-Eye ClickHouse — database init (DATABASE-3)
-- Blueprint: Part 8 (analytical/investigation store, l.305); Part 9.2 (l.357).
-- -----------------------------------------------------------------------------
-- Creates the `hawkeye` analytics database. All investigation tables live here.
-- On a cluster, run with `ON CLUSTER hawkeye_cluster` (apply_ddl.sh --mode replicated).
-- =============================================================================
CREATE DATABASE IF NOT EXISTS hawkeye;
