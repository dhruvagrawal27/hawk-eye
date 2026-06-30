#!/usr/bin/env bash
# Restore tooling (PLATFORM-26, blueprint Part 30.1). Reconstitutes from the latest backup
# and VALIDATES (row counts). A backup you haven't restored is a hope, not a plan.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="ops/backup/out"
DB="governance/db/governance.db"

LATEST="$(ls -t "$OUT"/governance-*.db 2>/dev/null | head -1)"
if [ -z "${LATEST:-}" ]; then echo "no backup found in $OUT; run ops/backup/backup.sh"; exit 1; fi

count() { python3 - "$1" <<'PY'
import sqlite3,sys
c=sqlite3.connect(sys.argv[1])
t=[r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print(sum(c.execute(f"select count(*) from {x}").fetchone()[0] for x in t))
PY
}

echo "[restore] restoring from $LATEST"
N_SRC=$(count "$LATEST")
cp "$LATEST" "$DB"
N_DST=$(count "$DB")
echo "[restore] rows backup=$N_SRC restored=$N_DST"
[ "$N_SRC" = "$N_DST" ] && echo "RESTORE: PASS (validated)" || { echo "RESTORE: FAIL"; exit 1; }
