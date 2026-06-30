#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye ClickHouse — DDL applier (DATABASE-3/4)
# Applies ddl/*.sql + indexes.sql + search_helpers.sql in order, idempotently.
# -----------------------------------------------------------------------------
# Engine toggle (prompt §7 "MergeTree fallback ... toggle via a config var"):
#   CH_ENGINE_MODE=single      -> ReplacingMergeTree            (default; single node)
#   CH_ENGINE_MODE=replicated  -> ReplicatedReplacingMergeTree  (+ ON CLUSTER, cluster.xml)
#
# Connection (env, with dev defaults matching deploy/compose/.env):
#   CH_HOST=localhost CH_PORT=9000 CH_USER=hawkeye CH_PASSWORD=hawkeye_dev_pw
# Override the client entirely with CH_CLIENT, e.g.:
#   CH_CLIENT="docker exec -i hawkeye-clickhouse clickhouse-client" ./apply_ddl.sh
#
# Usage:  ./apply_ddl.sh [--materialize]
# =============================================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CH_HOST="${CH_HOST:-localhost}"
CH_PORT="${CH_PORT:-9000}"
CH_USER="${CH_USER:-hawkeye}"
CH_PASSWORD="${CH_PASSWORD:-hawkeye_dev_pw}"
CH_ENGINE_MODE="${CH_ENGINE_MODE:-single}"
CLUSTER="${CH_CLUSTER:-hawkeye_cluster}"
MATERIALIZE=0
[[ "${1:-}" == "--materialize" ]] && MATERIALIZE=1

if [[ -n "${CH_CLIENT:-}" ]]; then
  BASE_CLIENT="${CH_CLIENT}"
elif command -v clickhouse-client >/dev/null 2>&1; then
  BASE_CLIENT="clickhouse-client --host ${CH_HOST} --port ${CH_PORT} --user ${CH_USER} --password ${CH_PASSWORD}"
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^hawkeye-clickhouse$'; then
  BASE_CLIENT="docker exec -i hawkeye-clickhouse clickhouse-client --user ${CH_USER} --password ${CH_PASSWORD}"
else
  echo "[apply_ddl] ERROR: no clickhouse-client found (local or container). Set CH_CLIENT." >&2
  exit 2
fi

log() { printf '[apply_ddl] %s\n' "$*"; }

# Rewrite engine for the replicated topology (uses default_replica_path from cluster.xml).
transform() {
  local file="$1"
  if [[ "$CH_ENGINE_MODE" == "replicated" ]]; then
    sed -e "s/ENGINE = ReplacingMergeTree(/ENGINE = ReplicatedReplacingMergeTree(/g" \
        -e "s/^CREATE TABLE IF NOT EXISTS \(hawkeye\.[a-z_0-9]*\)/CREATE TABLE IF NOT EXISTS \1 ON CLUSTER ${CLUSTER}/" \
        -e "s/^CREATE VIEW IF NOT EXISTS \(hawkeye\.[a-z_0-9]*\)/CREATE VIEW IF NOT EXISTS \1 ON CLUSTER ${CLUSTER}/" \
        -e "s/^CREATE DATABASE IF NOT EXISTS hawkeye;/CREATE DATABASE IF NOT EXISTS hawkeye ON CLUSTER ${CLUSTER};/" \
        "$file"
  else
    cat "$file"
  fi
}

run_sql() { echo "$1" | ${BASE_CLIENT} --multiquery; }

# Run a file, optionally with the experimental full-text flag (with version fallback).
run_file() {
  local file="$1" fulltext="${2:-0}"
  local sql; sql="$(transform "$file")"
  if [[ "$fulltext" == "1" ]]; then
    # Try modern flag, then legacy, then none — versions renamed inverted->full_text.
    echo "$sql" | ${BASE_CLIENT} --allow_experimental_full_text_index=1 --multiquery 2>/dev/null && return 0
    echo "$sql" | ${BASE_CLIENT} --allow_experimental_inverted_index=1 --multiquery 2>/dev/null && return 0
    echo "$sql" | ${BASE_CLIENT} --multiquery
  else
    echo "$sql" | ${BASE_CLIENT} --multiquery
  fi
}

log "mode=${CH_ENGINE_MODE} client='${BASE_CLIENT%% *} ...'"

# 1) database + tables (ordered) ----------------------------------------------
for f in "${HERE}"/ddl/00_init.sql "${HERE}"/ddl/0[1-9]_*.sql; do
  [[ -e "$f" ]] || continue
  log "applying $(basename "$f")"
  run_file "$f" 0
done

# 2) indices (full-text needs the experimental flag) --------------------------
log "applying indexes.sql (inverted/full-text + skip indices)"
run_file "${HERE}/indexes.sql" 1

# 3) parameterized search-helper views ----------------------------------------
log "applying search_helpers.sql"
run_file "${HERE}/search_helpers.sql" 0

# 4) optionally materialize indices over existing parts -----------------------
if [[ "$MATERIALIZE" == "1" && -f "${HERE}/materialize_indexes.sql" ]]; then
  log "materializing indices over existing parts"
  run_file "${HERE}/materialize_indexes.sql" 1
fi

log "done. Verify: SELECT name, engine, storage_policy FROM system.tables WHERE database='hawkeye';"
