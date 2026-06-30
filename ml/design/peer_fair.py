"""Peer-relative scoring (ML-9; blueprint Part 16/29, 19.2).

Scoring against an entity's PEER GROUP (not an absolute threshold) is the load-bearing
fairness + evasion-resistance primitive: it normalises out role/branch/department base
rates so "anomalous for your peers" — not "high in absolute terms" — drives the score.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def peer_relative_scores(
    scores: pd.Series,
    peer_groups: pd.Series,
    *,
    min_group: int = 3,
    fallback_global: bool = True,
) -> pd.Series:
    """Z-score each entity's score within its peer group (robust to tiny groups).

    Groups smaller than ``min_group`` fall back to the global distribution (if enabled),
    so a singleton peer group can't look artificially extreme.
    """
    s = pd.to_numeric(scores, errors="coerce").astype(float)
    pg = peer_groups.reindex(s.index).astype(str)
    global_mu, global_sd = float(s.mean()), float(s.std()) or 1.0
    out = pd.Series(index=s.index, dtype=float)
    for group, idx in pg.groupby(pg).groups.items():
        vals = s.loc[idx]
        if len(vals) >= min_group and float(vals.std()) > 0:
            mu, sd = float(vals.mean()), float(vals.std())
        elif fallback_global:
            mu, sd = global_mu, global_sd
        else:
            mu, sd = float(vals.mean()), (float(vals.std()) or 1.0)
        out.loc[idx] = (vals - mu) / (sd if sd > 0 else 1.0)
    return out.fillna(0.0)


def peer_relative_unit(scores: pd.Series, peer_groups: pd.Series, **kw) -> pd.Series:
    """Peer-relative z-scores squashed to [0,1] via a logistic (for fusion-ready scores)."""
    z = peer_relative_scores(scores, peer_groups, **kw)
    return 1.0 / (1.0 + np.exp(-z))


class PeerRelativeScorer:
    """Wrap any per-entity score map so output is peer-relative, not absolute."""

    def __init__(self, peer_group_of: pd.Series, *, min_group: int = 3) -> None:
        self.peer_group_of = peer_group_of.astype(str)
        self.min_group = min_group

    def transform(self, scores: pd.Series) -> pd.Series:
        pg = self.peer_group_of.reindex(scores.index).fillna("__global__")
        return peer_relative_unit(scores, pg, min_group=self.min_group)


def peer_group_from_features(
    entity_features: pd.DataFrame, events: Optional[pd.DataFrame] = None
) -> pd.Series:
    """Best-effort peer group per employee: prefer DATA's actor.peer_group, else by dept/role."""
    if (
        events is not None
        and "actor.peer_group" in events.columns
        and "actor.employee_id" in events.columns
    ):
        pg = (
            events[["actor.employee_id", "actor.peer_group"]]
            .dropna()
            .drop_duplicates("actor.employee_id")
            .set_index("actor.employee_id")["actor.peer_group"]
            .astype(str)
        )
        return pg.reindex(entity_features.index).fillna("__global__")
    return pd.Series("__global__", index=entity_features.index, name="peer_group")
