"""Tests for the ingest workstream (DATA-3/4/5/16/17).

Plain test_* functions, bare assert, runnable by data/tests/run.py (no pytest).
Each test builds its own tiny inputs and asserts behaviour. Fast (small N).
"""
from __future__ import annotations

from data.config import Topics
from data.eventbus import InProcessBus
from data.ingest.count_recon import CountReconciler, reconcile_counts
from data.ingest.normalizer import NormalizerSinks, ingest, normalize
from data.ingest.recon.swift_cbs_join import RECON_SIGNAL, reconcile
from data.ingest.reliability import (
    BackpressureBuffer,
    DeadLetterQueue,
    Deduper,
    ReliableIngest,
    retry_with_backoff,
)
from data.infra.kafka import (
    PARTITIONING_POLICY,
    all_topics,
    make_consumer,
    make_producer,
    partition_for,
)
from data.streaming.flink_jobs import (
    KeyedWindowJob,
    SlidingWindow,
    compute_windowed_features,
    velocity_1h,
)


# ---------- helpers ----------------------------------------------------------
def _cbs_row(emp="EMP-aaaa", ts="2026-06-30T10:00:00Z", amount=1000, **kw):
    row = {"employee_id": emp, "verb": "post_payment", "ts": ts, "channel": "cbs",
           "amount": amount, "cbs_ref": "REF1"}
    row.update(kw)
    return row


def _swift_ev(emp="EMP-bbbb", ts="2026-06-30T02:00:00Z", ref="REF9",
              instrument="LoU-1"):
    return {
        "event_id": "evt_swift1", "ts": ts,
        "actor": {"employee_id": emp, "role": "swift_op", "branch": "BR-1"},
        "action": {"verb": "swift_message", "channel": "swift"},
        "object": {"instrument": instrument, "amount": 4800000, "currency": "INR"},
        "context": {"ts": ts, "is_off_hours": True},
        "linkage": {"swift_ref": ref, "cbs_ref": None},
    }


def _cbs_ev(emp="EMP-cccc", ts="2026-06-30T02:05:00Z", ref="REF9"):
    return {
        "event_id": "evt_cbs1", "ts": ts,
        "actor": {"employee_id": emp, "role": "ops", "branch": "BR-1"},
        "action": {"verb": "post_payment", "channel": "cbs"},
        "object": {"amount": 4800000, "currency": "INR"},
        "context": {"ts": ts},
        "linkage": {"swift_ref": None, "cbs_ref": ref},
    }


# ---------- DATA-5: normalizer idempotency -----------------------------------
def test_normalizer_idempotent_event_id():
    raw = _cbs_row()
    a = normalize(raw, "cbs")
    b = normalize(dict(raw), "cbs")          # same logical row -> same id
    assert a.event_id == b.event_id
    assert a.event_id.startswith("evt_")
    # a different stable field changes the id
    c = normalize(_cbs_row(amount=2000), "cbs")
    assert c.event_id != a.event_id


def test_normalizer_maps_l0_fields_and_off_hours():
    ev = normalize(_cbs_row(ts="2026-06-30T02:30:00Z"), "cbs")
    d = ev.to_dict()
    assert d["actor"]["employee_id"] == "EMP-aaaa"
    assert d["action"]["verb"] == "post_payment"
    assert d["object"]["currency"] == "INR"
    # 02:30 is off-hours (night) -> derived True
    assert d["context"]["is_off_hours"] is True


def test_ingest_writes_to_bus_and_history():
    bus = InProcessBus()
    seen = []
    bus.subscribe(Topics.EVENTS_RAW, lambda m: seen.append(m))

    class _Hist:
        def __init__(self):
            self.rows = []

        def write(self, row):
            self.rows.append(row)

    hist = _Hist()
    sinks = NormalizerSinks(bus=bus, topic=Topics.EVENTS_RAW, history=hist)
    ev = ingest(_cbs_row(), "cbs", sinks)
    assert ev is not None
    assert len(seen) == 1 and len(hist.rows) == 1
    assert seen[0]["event_id"] == ev.event_id


# ---------- DATA-16: SWIFT<->CBS recon ---------------------------------------
def test_recon_fires_on_swift_without_cbs():
    bus = InProcessBus()
    sig = []
    bus.subscribe(Topics.EVENTS_SIGNALS, lambda m: sig.append(m))
    # a SWIFT instrument with NO matching CBS posting (the PNB mechanism)
    emitted = reconcile([_swift_ev(ref="REF-NOCBS")], bus=bus)
    assert len(emitted) == 1
    assert emitted[0]["signal"] == RECON_SIGNAL
    assert emitted[0]["reason"] == "swift_without_cbs"
    assert len(sig) == 1                      # published on events.signals


def test_recon_quiet_on_matched_pair():
    emitted = reconcile([_swift_ev(ref="REF9"), _cbs_ev(ref="REF9")])
    assert emitted == []                      # matched -> no mismatch


def test_recon_mixed_only_unmatched_fires():
    events = [
        _swift_ev(emp="EMP-1", ref="MATCH"),
        _cbs_ev(emp="EMP-2", ref="MATCH"),
        _swift_ev(emp="EMP-3", ref="LONE"),   # no CBS partner -> fires
    ]
    emitted = reconcile(events)
    assert len(emitted) == 1
    assert emitted[0]["linkage"]["swift_ref"] == "LONE"


# ---------- DATA-17: reliability ---------------------------------------------
def test_deduper_drops_duplicate_event_id():
    d = Deduper()
    assert d.is_new("evt_x") is True
    assert d.is_new("evt_x") is False         # duplicate dropped
    assert d.dropped == 1
    assert "evt_x" in d


def test_ingest_dedupe_via_reliable_handle():
    processed = []
    ri = ReliableIngest(process=lambda m: processed.append(m))
    assert ri.handle("evt_1", {"a": 1}) == "accepted"
    assert ri.handle("evt_1", {"a": 1}) == "duplicate"
    assert len(processed) == 1


def test_dead_letter_queue_captures_poison():
    def boom(_m):
        raise ValueError("poison")

    ri = ReliableIngest(process=boom, retries=1)
    assert ri.handle("evt_bad", {"x": 1}) == "dead_lettered"
    assert len(ri.dlq) == 1
    assert "ValueError" in ri.dlq.reasons()[0]


def test_backpressure_rejects_when_full():
    buf = BackpressureBuffer(capacity=2)
    assert buf.offer(1) and buf.offer(2)
    assert buf.offer(3) is False              # full -> backpressure
    assert buf.rejected == 1


def test_retry_with_backoff_eventually_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return "ok"

    assert retry_with_backoff(flaky, retries=5) == "ok"
    assert calls["n"] == 3


# ---------- DATA-17: count reconciliation ------------------------------------
def test_count_recon_detects_feed_loss():
    rec = CountReconciler(tolerance=0.0)
    for _ in range(8):
        rec.record_event({"action": {"channel": "cbs"}})
    for _ in range(5):
        rec.record_event({"action": {"channel": "swift"}})
    # source-of-truth says swift should have 10 -> silent loss of 5
    losses = rec.feed_loss({"cbs": 8, "swift": 10})
    assert len(losses) == 1
    assert losses[0].source == "swift"
    assert losses[0].shortfall_fraction == 0.5


def test_count_recon_one_shot_ok():
    events = [{"action": {"channel": "cbs"}} for _ in range(3)]
    results = reconcile_counts(events, {"cbs": 3})
    assert all(r.ok for r in results)


# ---------- DATA-4: windowed features ----------------------------------------
def test_velocity_window_positive_on_burst():
    emp = "EMP-burst"
    # 5 events within ~5 minutes -> 1h sliding velocity should be 5
    events = []
    for i in range(5):
        events.append({
            "event_id": f"evt_{i}",
            "ts": f"2026-06-30T10:0{i}:00Z",
            "actor": {"employee_id": emp},
            "action": {"verb": "post_payment", "channel": "cbs"},
        })
    job = velocity_1h(slide_s=60.0)
    job.run(events)
    assert job.latest(emp) == 5
    assert job.latest(emp) > 0


def test_compute_windowed_features_per_entity():
    events = [
        {"event_id": "e1", "ts": "2026-06-30T10:00:00Z",
         "actor": {"employee_id": "EMP-A"}, "action": {"verb": "login"}},
        {"event_id": "e2", "ts": "2026-06-30T10:10:00Z",
         "actor": {"employee_id": "EMP-A"}, "action": {"verb": "post"}},
        {"event_id": "e3", "ts": "2026-06-30T10:20:00Z",
         "actor": {"employee_id": "EMP-B"}, "action": {"verb": "login"}},
    ]
    feats = compute_windowed_features(events)
    assert feats["EMP-A"]["velocity_1h"] == 2
    assert feats["EMP-B"]["velocity_1h"] == 1


def test_sliding_window_evicts_old_events():
    emp = "EMP-evict"
    job = KeyedWindowJob(window=SlidingWindow(size_s=3600.0, slide_s=60.0),
                         aggregate=lambda k, evs: len(evs))
    old = {"ts": "2026-06-30T08:00:00Z", "actor": {"employee_id": emp},
           "action": {"verb": "x"}}
    new = {"ts": "2026-06-30T10:00:00Z", "actor": {"employee_id": emp},
           "action": {"verb": "y"}}
    job.process(old)
    job.process(new)                          # 2h later -> old evicted from 1h window
    assert job.latest(emp) == 1


# ---------- DATA-3: kafka topology + clients ---------------------------------
def test_topics_defined_and_partitioning_keyed_by_entity():
    topics = all_topics()
    assert Topics.EVENTS_RAW in topics
    assert Topics.EVENTS_SIGNALS in topics
    assert "entity" in PARTITIONING_POLICY.lower()
    # same employee -> same partition (per-entity ordering)
    m1 = {"actor": {"employee_id": "EMP-K"}, "event_id": "e1"}
    m2 = {"actor": {"employee_id": "EMP-K"}, "event_id": "e2"}
    assert partition_for(Topics.EVENTS_RAW, m1) == partition_for(Topics.EVENTS_RAW, m2)


def test_producer_consumer_roundtrip_fallback():
    bus = InProcessBus()
    prod = make_producer(bus=bus, use_kafka=False)
    cons = make_consumer(bus=bus, use_kafka=False)
    cons.subscribe(Topics.EVENTS_RAW)
    msg = normalize(_cbs_row(), "cbs").to_dict()
    prod.produce(Topics.EVENTS_RAW, msg)
    got = cons.poll_all()
    assert len(got) == 1
    assert got[0]["event_id"] == msg["event_id"]
