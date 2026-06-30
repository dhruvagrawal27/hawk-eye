"""DATA feature-engineering catalogue (DATA-19/20/21/22; blueprint Part 6.1-6.6).

Every feature is a pure function over a pandas DataFrame of *flattened* L0 events
(columns like `actor.employee_id`, `action.verb`, `object.amount`, `context.ts`,
`context.is_off_hours`, `linkage.*`) returning a per-entity value/Series. Feature
names use `data.config.feature_key()`. Hard deps: numpy/pandas only. Optional libs
(networkx, featuretools, redis) are guarded with pure-python fallbacks.

Status: REAL (runs on synthetic/flattened L0 data with numpy/pandas only).
"""
from __future__ import annotations

__all__ = [
    "baselines",
    "identity_access",
    "transaction",
    "data_layer",
    "change_hr",
    "graph",
    "temporal",
    "dfs_featuretools",
]
