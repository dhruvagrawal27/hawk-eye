"""Elliptic (Bitcoin) graph loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): 200k+ node transaction graph, labelled illicit/licit. Use it to
prototype the GRAPH layer (L5) -- node/edge features, centrality, motif detection.

Mapping: GRAPH form -> two DataFrames (`nodes` with features + class, `edges` txId1->txId2).
Class convention (Elliptic): 1 = illicit, 2 = licit, "unknown" = unlabelled. We normalise
to {1: fraud, 0: benign, -1: unknown} so PU-learning hooks (DATA-23) can exploit unknowns.

Leakage caveats:
- The bulk of nodes are UNLABELLED ("unknown") -> this is a Positive-Unlabelled setting,
  not a clean binary one; do not treat unknown as negative (that is a labelling leak/bias).
- Temporal: nodes carry a time step; respect it in temporal splits (DATA-24).
- No drop-in pre-trained model for the bank (Part 5.3); graph-layer prototype only.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from data.config import SimConfig


class EllipticLoader:
    name = "elliptic"
    purpose = "graph layer L5 (Elliptic Bitcoin tx graph)"
    leakage_caveats = "most nodes unlabelled (PU setting); do not treat unknown as benign."

    def load(self, path: str) -> dict[str, pd.DataFrame]:
        """Load real Elliptic CSVs from `path` (features/classes/edgelist) if present;
        else a tiny synthetic graph stand-in."""
        if path and os.path.isdir(path):
            feats = os.path.join(path, "elliptic_txs_features.csv")
            classes = os.path.join(path, "elliptic_txs_classes.csv")
            edges = os.path.join(path, "elliptic_txs_edgelist.csv")
            if all(os.path.isfile(p) for p in (feats, classes, edges)):
                nodes = pd.read_csv(feats, header=None)
                nodes = nodes.rename(columns={0: "txId", 1: "time_step"})
                cls = pd.read_csv(classes)
                cls["class"] = cls["class"].map({"1": 1, "2": 0, "unknown": -1}).fillna(-1)
                nodes = nodes.merge(cls, left_on="txId", right_on="txId", how="left")
                return {"nodes": nodes, "edges": pd.read_csv(edges)}
        return self.synthetic()

    def synthetic(self, cfg: Optional[SimConfig] = None) -> dict[str, pd.DataFrame]:
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        n = 60
        # classes: mostly unknown (-1), a few illicit (1) and licit (0) -> PU shape
        cls = np.full(n, -1)
        cls[rng.choice(n, 6, replace=False)] = 0
        cls[rng.choice(np.where(cls == -1)[0], 3, replace=False)] = 1
        nodes = pd.DataFrame({
            "txId": np.arange(n),
            "time_step": rng.integers(1, 10, n),
            "f0": rng.normal(0, 1, n),
            "f1": rng.normal(0, 1, n),
            "class": cls,
        })
        # random DAG-ish edges
        src = rng.integers(0, n, n * 2)
        dst = rng.integers(0, n, n * 2)
        edges = pd.DataFrame({"txId1": src, "txId2": dst})
        edges = edges[edges["txId1"] != edges["txId2"]].reset_index(drop=True)
        return {"nodes": nodes, "edges": edges}


def demo() -> dict[str, pd.DataFrame]:
    return EllipticLoader().synthetic()
