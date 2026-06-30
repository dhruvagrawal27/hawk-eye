#!/usr/bin/env python3
"""Topology smoke test (PLATFORM-4, blueprint Part 9.1 / Part 18).

Flows a synthetic L0 event through the reference topology and asserts an alert lands.
Two layers, so it is meaningful with the stack up AND green in CI without Docker:

  1. IN-PROCESS (always): score the canonical synthetic burst through the reference
     scorer (degradation-switch app) and assert a high-severity, status=open alert.
     This is the deterministic core — proves the L0 -> ... -> alert hop and ALERT-ONLY.
  2. KAFKA ROUND-TRIP (when a broker is reachable on localhost:29092): produce the L0
     event to hawkeye.events.l0, score, produce the alert to hawkeye.alerts, consume it
     back, and assert. Exercises the real transport + topic topology.

Exit 0 on success, non-zero on any assertion failure.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "degradation-switch"))

from dswitch import scoring  # noqa: E402

# Canonical synthetic burst (DATA's create_beneficiary -> approve_payment scenario;
# BACKEND.md §1 + blueprint Part 24.5/25.6 example).
EVENT = {
    "event_id": "evt_smoke_0001",
    "ts": "2026-06-30T02:14:07Z",
    "actor": {"employee_id": "EMP-7f3a", "role": "ops_maker", "dept": "trade_finance",
              "branch": "BR-219", "tenure_days": 2840, "leaver_flag": False},
    "action": {"verb": "approve_payment", "channel": "cbs", "maker_checker": "checker"},
    "object": {"beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": 4_800_000,
               "currency": "INR", "new_beneficiary": True, "beneficiary_age_min": 27},
    "context": {"src_ip": "10.20.4.31", "device": "WS-114", "geo": "Mumbai",
                "session_id": "sess_55e1", "layer": "application", "is_off_hours": True},
    "linkage": {"maker_employee_id": "EMP-1a09", "maker_checker_isolated_pair": True},
}
BROKER = os.environ.get("KAFKA_BOOTSTRAP_HOST", "localhost:29092")


def in_process() -> dict:
    print("[smoke] (1) in-process scoring of synthetic L0 event ...")
    alert = scoring.score_event(EVENT, mode="full",
                                layer_scores={"L2_unsupervised": 0.82, "L3_gbdt": 0.78, "L5_graph": 0.7})
    assert alert is not None, "no alert produced for a known-fraud burst"
    assert alert["status"] == "open", "ALERT-ONLY violated: alert is not human-pending"
    assert alert["risk_score"] >= 65, f"risk too low: {alert['risk_score']}"
    assert "L1_rules" in alert["contributing_layers"]
    codes = [rc.get("code") for rc in alert["reason_codes"] if rc.get("source") == "rule"]
    assert "NEW_BENEFICIARY_THEN_HIGHVALUE" in codes, codes
    print(f"[smoke]     -> alert {alert['alert_id']} risk={alert['risk_score']} "
          f"sev={alert['severity']} reasons={codes}")
    return alert


def kafka_round_trip(alert: dict) -> bool:
    try:
        from confluent_kafka import Consumer, Producer
        from confluent_kafka.admin import AdminClient
    except Exception:
        print("[smoke] (2) confluent-kafka not installed; skipping Kafka round-trip (CI mode).")
        return True
    try:
        admin = AdminClient({"bootstrap.servers": BROKER})
        md = admin.list_topics(timeout=3)
        if "hawkeye.events.l0" not in md.topics:
            print("[smoke] (2) broker reachable but topics absent; is the stack up? skipping.")
            return True
    except Exception:
        print(f"[smoke] (2) no broker on {BROKER}; skipping Kafka round-trip (stack down).")
        return True

    print(f"[smoke] (2) Kafka round-trip via {BROKER} ...")
    p = Producer({"bootstrap.servers": BROKER})
    p.produce("hawkeye.events.l0", json.dumps(EVENT).encode())
    p.produce("hawkeye.alerts", json.dumps(alert).encode())
    p.flush(5)

    c = Consumer({"bootstrap.servers": BROKER, "group.id": f"smoke-{int(time.time())}",
                  "auto.offset.reset": "earliest"})
    c.subscribe(["hawkeye.alerts"])
    deadline = time.time() + 10
    found = False
    while time.time() < deadline:
        msg = c.poll(1.0)
        if msg and not msg.error():
            got = json.loads(msg.value())
            if got.get("source_event_id") == EVENT["event_id"] or got.get("alert_id") == alert["alert_id"]:
                found = True
                break
    c.close()
    assert found, "alert did not land on hawkeye.alerts within 10s"
    print("[smoke]     -> alert observed on hawkeye.alerts ✓")
    return True


def main() -> int:
    alert = in_process()
    kafka_round_trip(alert)
    print("\n[smoke] PASS — synthetic L0 event flowed to an alert (alert-only, human-pending).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"\n[smoke] FAIL — {e}", file=sys.stderr)
        raise SystemExit(1)
