"""Agent-based synthetic simulator core (DATA-7/10).

Blueprint Part 21.1 (l.791-808), Part 5.5 (l.203-206), Part 24.5(d) (worked burst).

SimPy/Mesa are OPTIONAL (guarded). The pure numpy/pandas event-loop fallback below is the
default so the simulator imports and runs with only numpy/pandas/pyarrow installed. The
discrete day-by-day loop preserves the diurnal/weekly rhythms and per-event ordering that
naive tabular generators destroy (Part 5.5) — behavioural realism comes from this sim.

Deterministic: all randomness derives from numpy.random.default_rng(SimConfig.seed).
Status: REAL (synthetic-only, ALERT-ONLY).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from data.config import SimConfig, make_id
from data.schemas import Action, Actor, Context, L0Event, Linkage, ObjectRef
from data.schemas.label import Label
from data.sim.labels import benign_label, select_fraud_actors
from data.sim.normal_behaviour import generate_normal
from data.sim.population import generate_population
from data.sim.scenarios import LANES, REGISTRY

# SimPy/Mesa are optional agent-sim frameworks (Part 21.1). We guard the import and fall
# back to the deterministic numpy loop below; the flag is exposed for diagnostics.
try:  # pragma: no cover - exercised only when simpy is installed
    import simpy  # type: ignore  # noqa: F401

    HAVE_SIMPY = True
except Exception:
    HAVE_SIMPY = False


# A Monday anchor so weekday rhythms line up deterministically.
_DEFAULT_START = datetime(2026, 1, 5, tzinfo=timezone.utc)


class Simulator:
    """Runs population + normal behaviour across days and injects rare fraud scenarios.

    Usage:
        sim = Simulator(SimConfig(n_employees=100, days=7))
        events, labels = sim.run()
    """

    def __init__(self, cfg: SimConfig | None = None, start: datetime | None = None) -> None:
        self.cfg = cfg or SimConfig()
        self.start = (start or _DEFAULT_START).astimezone(timezone.utc)
        self.rng = np.random.default_rng(self.cfg.seed)
        self.population = generate_population(self.cfg)

    # ---- main run -----------------------------------------------------------
    def run(self) -> tuple[list[L0Event], list[Label]]:
        """Return (events, labels). Labels are 1:1 with events (benign or fraud)."""
        events: list[L0Event] = []
        labels: list[Label] = []

        # 1) benign background traffic for the whole population
        benign = generate_normal(self.population, self.start, self.cfg.days, self.rng)
        for ev in benign:
            events.append(ev)
            labels.append(benign_label(ev.event_id, ev.actor.employee_id))

        # 2) inject a rare subset of fraud actors with scenario traces.
        # Guarantee coverage of all 12 typologies (so labels demonstrably include each),
        # while honouring the rare fraud-actor rate for the actor pool size.
        scenario_ids = list(REGISTRY.keys())
        n_fraud = max(len(scenario_ids),
                      int(round(len(self.population) * self.cfg.fraud_actor_rate)))
        fraud_actors = select_fraud_actors(
            self.population, self.cfg.fraud_actor_rate, self.rng, min_actors=n_fraud
        )

        for i, sid in enumerate(scenario_ids):
            inject = REGISTRY[sid]
            # base_ts for each scenario lands a few days into the run, within the window
            day_offset = int(self.rng.integers(0, max(1, self.cfg.days)))
            base_ts = self.start + timedelta(days=day_offset)
            trace = inject(self.rng, self.population, base_ts)
            for ev, lb in trace:
                # ensure lane tag is consistent with the registry
                if lb.lane is None:
                    lb.lane = LANES.get(sid)
                events.append(ev)
                labels.append(lb)

        return events, labels

    def run_records(self) -> tuple[list[dict], list[dict]]:
        """Same as run() but returns plain dicts (for sinks / parquet)."""
        events, labels = self.run()
        return [e.to_dict() for e in events], [lb.to_dict() for lb in labels]


# ---- Worked burst (DATA-10 / Part 24.5d) ------------------------------------
def replay_worked_burst(seed: int = 1405) -> list[tuple[L0Event, Label]]:
    """Reproduce the Part 24.5(d) worked burst EXACTLY (deterministic, on demand).

    Sequence:
      02:14:07 create_beneficiary BEN-9b1c off-hours by maker EMP-7f3a
      02:33:10 approve_payment INR 48,00,000 (amount=4800000, currency INR) to BEN-9b1c
               by checker EMP-1a09
      02:33:11 graph edge maker EMP-7f3a <-> checker EMP-1a09 (ring RNG-*)

    Returns the labelled positive trace. This is what the demo/pilot replays.
    """
    rng = np.random.default_rng(seed)
    # Use the exact ids from the blueprint sample so the burst is byte-recognisable.
    maker = Actor(employee_id="EMP-7f3a", role="ops_maker", dept="trade_finance",
                  branch="BR-219", tenure_days=2840, manager_id="EMP-1a09",
                  peer_group="PG-ops-tf", privileged_flag=False)
    checker = Actor(employee_id="EMP-1a09", role="ops_checker", dept="trade_finance",
                    branch="BR-219", tenure_days=4100, manager_id=None,
                    peer_group="PG-ops-tf", privileged_flag=False)
    ben_id = "BEN-9b1c"
    acct = "ACCT-4d22"
    ring_id = make_id("ring", maker.employee_id, checker.employee_id)

    def _ctx(ts: str, off: bool) -> Context:
        return Context(ts=ts, src_ip="10.20.4.31", device="WS-114", geo="Mumbai",
                       session_id="sess_55e1", layer="application", is_off_hours=off, host=None)

    # 02:14:07 — create_beneficiary off-hours
    ts0 = "2026-06-30T02:14:07Z"
    e0 = L0Event(
        event_id=make_id("event", maker.employee_id, "create_beneficiary", ts0),
        ts=ts0, actor=maker,
        action=Action(verb="create_beneficiary", channel="cbs", maker_checker="maker"),
        object=ObjectRef(beneficiary_id=ben_id, account_id=acct, currency="INR"),
        context=_ctx(ts0, True),
        linkage=Linkage(maker_id=maker.employee_id, customer_account=acct),
    )
    l0 = Label(event_id=e0.event_id, is_fraud=True, scenario_id="beneficiary_then_approve",
               actor_id=maker.employee_id, ring_id=ring_id, lane="fast")

    # 02:33:10 — approve_payment INR 48,00,000
    ts1 = "2026-06-30T02:33:10Z"
    e1 = L0Event(
        event_id=make_id("event", checker.employee_id, "approve_payment", ts1),
        ts=ts1, actor=checker,
        action=Action(verb="approve_payment", channel="cbs", maker_checker="checker"),
        object=ObjectRef(beneficiary_id=ben_id, account_id=acct, amount=4_800_000,
                         currency="INR"),
        context=_ctx(ts1, True),
        linkage=Linkage(maker_id=maker.employee_id, checker_id=checker.employee_id,
                        customer_account=acct),
    )
    l1 = Label(event_id=e1.event_id, is_fraud=True, scenario_id="beneficiary_then_approve",
               actor_id=checker.employee_id, ring_id=ring_id, lane="fast")

    # 02:33:11 — graph edge (maker<->checker) recorded as an L0 event for L5
    ts2 = "2026-06-30T02:33:11Z"
    e2 = L0Event(
        event_id=make_id("event", maker.employee_id, "graph_edge", ts2),
        ts=ts2, actor=maker,
        action=Action(verb="graph_edge", channel="cbs", maker_checker=None),
        object=ObjectRef(beneficiary_id=ben_id, account_id=acct),
        context=_ctx(ts2, True),
        linkage=Linkage(maker_id=maker.employee_id, checker_id=checker.employee_id,
                        customer_account=acct),
    )
    l2 = Label(event_id=e2.event_id, is_fraud=True, scenario_id="maker_checker_ring",
               actor_id=maker.employee_id, ring_id=ring_id, lane="fast")
    _ = rng  # determinism anchor (kept for parity with other inject signatures)
    return [(e0, l0), (e1, l1), (e2, l2)]


def demo() -> tuple[list[L0Event], list[Label]]:
    return Simulator(SimConfig(n_employees=60, days=5, seed=11)).run()
