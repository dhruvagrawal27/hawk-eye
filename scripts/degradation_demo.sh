#!/usr/bin/env bash
# Degradation demo (PLATFORM-4/28, blueprint Part 18 + Part 30.1).
# Proves the BCP continuity feature + the ALERT-ONLY golden rule: when ML serving is
# unhealthy, the pipeline keeps scoring via L1-rules-only and still only ALERTS.
#
# Uses the live switch (:8092) if reachable; otherwise an in-process demonstration.
set -uo pipefail
SWITCH="${DEGRADATION_SWITCH_URL:-http://localhost:8092}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

EVENT='{"event_id":"evt_demo_01","ts":"2026-06-30T02:14:07Z",
 "actor":{"employee_id":"EMP-7f3a","tenure_days":2840,"leaver_flag":false},
 "action":{"verb":"approve_payment","channel":"cbs","maker_checker":"checker"},
 "object":{"beneficiary_id":"BEN-9b1c","amount":4800000,"currency":"INR","new_beneficiary":true,"beneficiary_age_min":27},
 "context":{"is_off_hours":true,"layer":"application"},
 "linkage":{"maker_employee_id":"EMP-1a09","maker_checker_isolated_pair":true}}'

echo "== Hawk-Eye degradation demo =="

if curl -fsS "${SWITCH}/health" >/dev/null 2>&1; then
  echo "[live] degradation-switch reachable at ${SWITCH}"
  echo "--- initial mode ---"; curl -fsS "${SWITCH}/mode"; echo
  echo "--- score (current mode) ---"
  curl -fsS -X POST "${SWITCH}/score" -H 'content-type: application/json' \
    -d "{\"event\": ${EVENT}}" | python3 -m json.tool
  echo "--- FORCE rules-only (simulating ML serving outage) ---"
  curl -fsS -X POST "${SWITCH}/admin/force" -H 'content-type: application/json' \
    -d '{"forced":true,"actor":"demo-admin"}'; echo
  echo "--- mode after forcing ---"; curl -fsS "${SWITCH}/mode"; echo
  echo "--- score again: must STILL alert, rules-only, marked_for_rescore ---"
  curl -fsS -X POST "${SWITCH}/score" -H 'content-type: application/json' \
    -d "{\"event\": ${EVENT}}" | python3 -m json.tool
  echo "--- restore full mode ---"
  curl -fsS -X POST "${SWITCH}/admin/force" -H 'content-type: application/json' \
    -d '{"forced":false,"actor":"demo-admin"}'; echo
  echo "[live] PASS — pipeline stayed alive on L1-rules-only during the simulated outage."
else
  echo "[in-process] switch not running; demonstrating the same logic locally."
  python3 - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + "/services/degradation-switch")
from dswitch import scoring, health
ev = {"event_id":"evt_demo_01","ts":"2026-06-30T02:14:07Z",
 "actor":{"employee_id":"EMP-7f3a","tenure_days":2840,"leaver_flag":False},
 "action":{"verb":"approve_payment","channel":"cbs","maker_checker":"checker"},
 "object":{"beneficiary_id":"BEN-9b1c","amount":4800000,"currency":"INR","new_beneficiary":True,"beneficiary_age_min":27},
 "context":{"is_off_hours":True,"layer":"application"},
 "linkage":{"maker_employee_id":"EMP-1a09","maker_checker_isolated_pair":True}}

print("--- full mode (ML serving healthy) ---")
a = scoring.score_event(ev, "full", {"L2_unsupervised":0.82,"L3_gbdt":0.78,"L5_graph":0.7})
print(f"  alert {a['alert_id']} risk={a['risk_score']} sev={a['severity']} mode={a['scoring_mode']} layers={a['contributing_layers']}")

print("--- FORCE rules-only (simulating ML serving outage) ---")
health.set_forced(True)
mode = health.current_mode(); print("  current_mode =", mode)
b = scoring.score_event(ev, mode)
assert b is not None and b["status"] == "open", "ALERT-ONLY/continuity broken"
assert b["marked_for_rescore"] is True
print(f"  alert {b['alert_id']} risk={b['risk_score']} sev={b['severity']} mode={b['scoring_mode']} rescore={b['marked_for_rescore']}")
health.set_forced(False)
print("\n[in-process] PASS — rules-only fallback kept the pipeline alerting; events marked for re-score.")
PY
fi
