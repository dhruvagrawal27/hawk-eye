#!/usr/bin/env bash
# DR restore drill (PLATFORM-27, blueprint Part 30.1). Runnable evidence:
#   backup -> teardown -> restore -> VALIDATE ROW COUNTS -> failover toggle -> RTO/RPO report.
# Operates on the governance DB (SQLite) for a self-contained demo; the same flow applies to
# Postgres/ClickHouse/audit/registry in prod (ops/backup/). MOCK: the *drill* is an org act;
# the script + report are real evidence.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DB="governance/db/governance.db"
BK_DIR="ops/backup/out"
OUT_DIR="ops/dr/out"
mkdir -p "$BK_DIR" "$OUT_DIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
START_EPOCH=$(date +%s)

echo "== Hawk-Eye DR restore drill ($TS) =="

# 0) ensure seeded
if [ ! -f "$DB" ] || ! python3 -c "import sqlite3,sys; c=sqlite3.connect('$DB'); n=c.execute(\"select count(*) from sqlite_master where type='table'\").fetchone()[0]; sys.exit(0 if n>0 else 1)" 2>/dev/null; then
  echo "[drill] seeding governance DB first ..."
  python3 governance/db/seed.py >/dev/null
fi

count_rows() {  # total rows across all governance tables
  python3 - "$DB" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print(sum(c.execute(f"select count(*) from {t}").fetchone()[0] for t in tables))
PY
}

N_BEFORE=$(count_rows)
echo "[drill] rows before: $N_BEFORE"

# 1) BACKUP (encrypted/immutable in prod -> object-lock; here a timestamped copy)
BK="$BK_DIR/governance-$TS.db"
cp "$DB" "$BK"
BACKUP_EPOCH=$(date +%s)
echo "[drill] backup -> $BK"

# 2) TEARDOWN (simulate primary loss)
rm -f "$DB"
echo "[drill] primary torn down"

# 3) RESTORE from backup
cp "$BK" "$DB"
echo "[drill] restored from backup"

# 4) VALIDATE ROW COUNTS
N_AFTER=$(count_rows)
echo "[drill] rows after : $N_AFTER"
if [ "$N_BEFORE" != "$N_AFTER" ]; then
  echo "[drill] FAIL — row count mismatch ($N_BEFORE != $N_AFTER)"; exit 1
fi

# 5) FAILOVER toggle (mark standby active)
echo "{\"active\":\"standby\",\"promoted_ts\":\"$TS\"}" > "$OUT_DIR/failover-state.json"
END_EPOCH=$(date +%s)

# 6) RTO/RPO report
RTO=$((END_EPOCH - START_EPOCH))     # time to restore + validate + failover
RPO=$((BACKUP_EPOCH - START_EPOCH))  # data-loss window since last good backup (here ~0)
REPORT="$OUT_DIR/drill-report-$TS.json"
cat > "$REPORT" <<JSON
{
  "drill_ts": "$TS",
  "target": "governance-db (sqlite; prod: postgres/clickhouse/audit/registry)",
  "rows_before": $N_BEFORE,
  "rows_after": $N_AFTER,
  "row_counts_match": true,
  "measured_rto_seconds": $RTO,
  "measured_rpo_seconds": $RPO,
  "failover": "promoted standby",
  "result": "PASS",
  "blueprint": "Part 30.1 (restore/DR/cyber-resilience drill)"
}
JSON
echo "[drill] PASS — RTO ${RTO}s, RPO ${RPO}s. Report: $REPORT"
cat "$REPORT"
