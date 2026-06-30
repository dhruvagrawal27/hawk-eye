"""Agent-based synthetic insider-fraud simulator package (DATA-7/8/9/10/11).

Blueprint Part 21.1 (agent-based simulator), 21.2 (generative augmentation),
5.5 (synthetic data), 24.5d (worked burst), Part 12 (typology coverage map).

Status: REAL on synthetic-only data. Emits labelled L0 events; never blocks anything
(golden rule 1: ALERT-ONLY) and never emits real PII (golden rule 2: ids via make_id).

Public surface:
- Simulator(SimConfig)  -> deterministic run producing (events, labels)
- generate_population(...)
- REGISTRY / LANES (scenarios) and the per-typology inject() functions
"""
from data.sim.population import Employee, generate_population  # noqa: F401
from data.sim.simulator import Simulator, replay_worked_burst  # noqa: F401
from data.sim.scenarios import REGISTRY, LANES  # noqa: F401
