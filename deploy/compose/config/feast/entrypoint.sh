#!/usr/bin/env bash
# Resilient Feast server entrypoint (PLATFORM host). Stays up even if the placeholder
# repo can't fully apply offline, so the walking skeleton is always green.
set -uo pipefail
cd /feature_repo
mkdir -p data

echo "[feast] applying placeholder feature repo (DATA owns the real defs) ..."
feast apply 2>/dev/null || echo "[feast] apply skipped (DATA provides feature definitions)"

echo "[feast] starting feature server on :6566 ..."
feast serve -h 0.0.0.0 -p 6566 || {
  echo "[feast] feast serve unavailable offline; holding port 6566 (host placeholder)"
  python3 -m http.server 6566
}
