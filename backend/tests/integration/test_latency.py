"""Latency budget (BACKEND §8 / blueprint Part 18.1).

Generous bounds for a CI rig — the point is to catch a gross regression, not to benchmark. Budget:
L1 rules <5 ms · L2+L3 ~5–30 ms · TreeSHAP ~5–20 ms · end-to-end ≤ ~300 ms.
"""

from __future__ import annotations

import time

from app.clients.feature_client import FeatureReader
from app.pipeline.online import OnlinePipeline
from app.store.alert_store import AlertStore
from rules_engine.engine import DEFAULT_ENGINE


def _burst(eid="evt_lat"):
    return {
        "event_id": eid,
        "ts": "2026-06-30T02:33:10Z",
        "actor": {"employee_id": "EMP-7f3a"},
        "action": {"verb": "approve_payment", "channel": "cbs"},
        "object": {"beneficiary_id": "BEN-9b1c", "amount": 4_800_000},
        "context": {"is_off_hours": True},
        "linkage": {},
    }


def test_l1_rules_fast():
    feats = {"minutes_since_new_beneficiary": 19}
    DEFAULT_ENGINE.evaluate(_burst(), feats)  # warm
    start = time.perf_counter()
    for _ in range(50):
        DEFAULT_ENGINE.evaluate(_burst(), feats)
    avg = (time.perf_counter() - start) / 50
    assert avg < 0.02, f"L1 rules avg {avg * 1000:.2f}ms exceeds budget"


def test_end_to_end_within_budget():
    p = OnlinePipeline(feature_reader=FeatureReader(), store=AlertStore(), short_circuit=False)
    start = time.perf_counter()
    p.process_full(_burst("evt_lat_e2e"))
    dur = time.perf_counter() - start
    assert dur < 0.3, f"end-to-end {dur * 1000:.2f}ms exceeds ~300ms budget"
