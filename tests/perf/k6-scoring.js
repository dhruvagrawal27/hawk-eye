// k6 load + soak test for the scoring path (PLATFORM-21, blueprint Part 31.1 / Part 30.2).
// Asserts p99 scoring latency within the SLO budget (observability/slo-definitions.yaml:
// p99 250ms) at target TPS, plus a soak stage. Run: k6 run tests/perf/k6-scoring.js
import http from "k6/http";
import { check } from "k6";

const SWITCH = __ENV.SWITCH_URL || "http://localhost:8092";

export const options = {
  scenarios: {
    sustained: { executor: "constant-arrival-rate", rate: 200, timeUnit: "1s",
                 duration: "2m", preAllocatedVUs: 50, maxVUs: 200 },        // target TPS
    burst:     { executor: "ramping-arrival-rate", startRate: 100, timeUnit: "1s",
                 startTime: "2m", stages: [{ target: 800, duration: "30s" },
                                           { target: 800, duration: "30s" },
                                           { target: 100, duration: "30s" }],
                 preAllocatedVUs: 100, maxVUs: 800 },
    soak:      { executor: "constant-arrival-rate", rate: 100, timeUnit: "1s",
                 startTime: "4m", duration: "10m", preAllocatedVUs: 50, maxVUs: 150 },
  },
  thresholds: {
    "http_req_duration{expected_response:true}": ["p(99)<250"],  // SLO p99 budget
    "checks": ["rate>0.99"],
  },
};

const EVENT = {
  event_id: "evt_perf", ts: "2026-06-30T02:14:07Z",
  actor: { employee_id: "EMP-7f3a", tenure_days: 2840 },
  action: { verb: "approve_payment", channel: "cbs", maker_checker: "checker" },
  object: { beneficiary_id: "BEN-9b1c", amount: 4800000, new_beneficiary: true, beneficiary_age_min: 27 },
  context: { is_off_hours: true, layer: "application" },
};

export default function () {
  const res = http.post(`${SWITCH}/score`, JSON.stringify({ event: EVENT }),
                        { headers: { "Content-Type": "application/json" } });
  check(res, { "status 200": (r) => r.status === 200,
               "alert present": (r) => r.json("alert") !== null });
}
