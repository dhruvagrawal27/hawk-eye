"""Label helpers + rare-fraud-actor enforcement (DATA-10).

Blueprint Part 21.1 #4 (l.806) ground-truth labelling, and 21.1 scale (l.808): a
realistic rare fraud rate (~0.1-1%). Builds Label objects (kept separate from events to
avoid leakage, Part 21.4) and selects which actors are fraudulent so the imbalance is
realistic.

Status: REAL (synthetic-only).
"""
from __future__ import annotations

import numpy as np

from data.schemas.label import Label
from data.sim.population import Employee


def make_label(
    event_id: str,
    is_fraud: bool,
    scenario_id: str | None = None,
    actor_id: str | None = None,
    ring_id: str | None = None,
    lane: str | None = None,
    label_source: str = "synthetic",
    confidence: float = 1.0,
) -> Label:
    """Construct a Label keyed by event_id (the only join key to L0 events)."""
    return Label(
        event_id=event_id,
        is_fraud=is_fraud,
        scenario_id=scenario_id,
        actor_id=actor_id,
        ring_id=ring_id,
        lane=lane,
        label_source=label_source,
        confidence=confidence,
    )


def benign_label(event_id: str, actor_id: str | None = None) -> Label:
    return make_label(event_id, is_fraud=False, actor_id=actor_id)


def select_fraud_actors(
    population: list[Employee],
    fraud_actor_rate: float,
    rng: np.random.Generator,
    min_actors: int = 1,
) -> list[Employee]:
    """Pick a rare subset of actors to be fraudulent.

    Enforces the configured rare rate (~0.1-1%) but guarantees at least `min_actors`
    so every requested scenario can be injected even on tiny local populations.
    """
    n = len(population)
    k = max(min_actors, int(round(n * fraud_actor_rate)))
    k = min(k, n)
    idx = rng.choice(n, size=k, replace=False)
    return [population[int(i)] for i in idx]


def fraud_actor_fraction(labels: list[Label], population: list[Employee]) -> float:
    """Observed fraction of actors that have at least one fraud label (for imbalance tests)."""
    fraud_actors = {lb.actor_id for lb in labels if lb.is_fraud and lb.actor_id}
    n = max(1, len({e.employee_id for e in population}))
    return len(fraud_actors) / n


def demo() -> list[Label]:
    rng = np.random.default_rng(1)
    return [
        make_label("evt_1", True, "beneficiary_then_approve", "EMP-aaaa", lane="fast"),
        benign_label("evt_2", "EMP-bbbb"),
    ]
