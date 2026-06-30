"""Tests for the synthetic simulator (DATA-7/8/9/10/11).

Plain test_* functions with bare assert (no pytest), runnable by data/tests/run.py.
Each test builds small inputs and asserts behaviour. Keeps N small for speed.
"""
from __future__ import annotations

from data.config import SimConfig
from data.schemas import validate_event
from data.sim.population import generate_population
from data.sim.scenarios import LANES, REGISTRY
from data.sim.simulator import Simulator, replay_worked_burst
from data.sim import augment


def _small_run():
    return Simulator(SimConfig(n_employees=60, days=4, seed=99)).run()


def test_population_shape():
    pop = generate_population(SimConfig(n_employees=80, seed=5))
    assert len(pop) == 80
    roles = {e.role for e in pop}
    # core roles needed by typologies should appear in a population of 80
    assert {"teller", "ops_maker", "ops_checker"} <= roles
    for e in pop:
        assert e.employee_id.startswith("EMP-")
        assert e.peer_group and e.branch


def test_all_events_validate():
    events, labels = _small_run()
    assert len(events) == len(labels)
    for ev in events:
        errs = validate_event(ev.to_dict())
        assert errs == [], f"invalid event {ev.event_id}: {errs}"


def test_all_twelve_scenarios_present_as_fraud():
    _events, labels = _small_run()
    fraud_sids = {lb.scenario_id for lb in labels if lb.is_fraud}
    for sid in REGISTRY:
        assert sid in fraud_sids, f"scenario {sid} missing from fraud labels"
    assert len(REGISTRY) == 12


def test_both_lanes_present():
    _events, labels = _small_run()
    lanes = {lb.lane for lb in labels if lb.is_fraud}
    assert "fast" in lanes
    assert "slow" in lanes
    # registry lane mapping is 8 fast + 4 slow
    assert sum(1 for v in LANES.values() if v == "fast") == 8
    assert sum(1 for v in LANES.values() if v == "slow") == 4


def test_swift_without_cbs_has_swift_ref_no_cbs():
    _events, labels = _small_run()
    events, _ = _small_run()
    # find a swift_without_cbs fraud event and assert linkage shape
    sid_events = {lb.event_id for lb in labels if lb.scenario_id == "swift_without_cbs"}
    matched = [e for e in events if e.event_id in sid_events]
    assert matched, "no swift_without_cbs events emitted"
    for e in matched:
        assert e.linkage.swift_ref is not None
        assert e.linkage.cbs_ref is None


def test_maker_checker_ring_has_ring_id():
    _events, labels = _small_run()
    ring_labels = [lb for lb in labels if lb.scenario_id == "maker_checker_ring" and lb.is_fraud]
    assert ring_labels
    for lb in ring_labels:
        assert lb.ring_id and lb.ring_id.startswith("RNG-")


def test_replay_worked_burst_has_approve_payment_4800000():
    trace = replay_worked_burst()
    verbs = {e.action.verb for e, _ in trace}
    assert "create_beneficiary" in verbs
    assert "approve_payment" in verbs
    approve = [e for e, _ in trace if e.action.verb == "approve_payment"][0]
    assert approve.object.amount == 4800000
    assert approve.object.currency == "INR"
    # off-hours create_beneficiary by maker
    create = [e for e, _ in trace if e.action.verb == "create_beneficiary"][0]
    assert create.context.is_off_hours is True
    assert create.action.maker_checker == "maker"
    # every burst event validates and is labelled fraud
    for e, lb in trace:
        assert validate_event(e.to_dict()) == []
        assert lb.is_fraud is True


def test_determinism_same_seed_same_event_ids():
    e1, _ = Simulator(SimConfig(n_employees=50, days=3, seed=42)).run()
    e2, _ = Simulator(SimConfig(n_employees=50, days=3, seed=42)).run()
    assert [e.event_id for e in e1] == [e.event_id for e in e2]


def test_different_seed_differs():
    e1, _ = Simulator(SimConfig(n_employees=50, days=3, seed=1)).run()
    e2, _ = Simulator(SimConfig(n_employees=50, days=3, seed=2)).run()
    assert [e.event_id for e in e1] != [e.event_id for e in e2]


def test_augment_minority_only_and_tagged():
    df = augment.demo()
    # synthetic rows are all fraud (minority) and tagged
    synth = df[df["__synthetic__"]]
    assert len(synth) > 0
    assert bool(synth["is_fraud"].all())
    # original non-synthetic majority count is unchanged (we only add minority rows)
    orig_majority = df[(~df["__synthetic__"]) & (~df["is_fraud"])]
    assert len(orig_majority) == 97


def test_negative_subsample_ratio():
    import pandas as pd

    df = pd.DataFrame({"x": range(100), "is_fraud": [True] * 5 + [False] * 95})
    sub = augment.negative_subsample(df, "is_fraud", ratio=5, seed=3)
    n_min = int(sub["is_fraud"].sum())
    n_maj = len(sub) - n_min
    assert n_min == 5
    assert n_maj == 25  # 5:1


def test_worked_burst_deterministic():
    a = replay_worked_burst()
    b = replay_worked_burst()
    assert [e.event_id for e, _ in a] == [e.event_id for e, _ in b]
