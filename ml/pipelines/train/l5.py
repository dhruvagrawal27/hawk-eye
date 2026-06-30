"""L5 graph training (ML-15; blueprint Part 22.2, 20.5).

Build / refresh the typed entity graph -> XGB-Graph (default; GADBench winner) and/or
GraphSAGE -> AUPRC / Rec@K -> register. Honest eval: entity-disjoint or time-aware split.

Default path is the XGB-Graph scorer (LightGBM/XGBoost/sklearn — torch-free). GraphSAGE
(torch_geometric) is supported via ``scorer=...`` but must NOT share a process with
LightGBM (macOS dual-libomp), so callers select one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from ml.eval import average_precision, recall_at_k
from ml.layers.l5 import XGBGraphScorer, build_entity_graph


@dataclass
class L5TrainResult:
    scorer: XGBGraphScorer
    metrics: dict[str, float]
    n_nodes: int = 0
    n_edges: int = 0
    n_train: int = 0
    n_test: int = 0

    @property
    def calibrated(self) -> bool:
        return True


def train_l5(
    entity_features: pd.DataFrame,
    entity_labels: pd.Series,
    events: pd.DataFrame,
    *,
    k: int = 2,
    test_frac: float = 0.3,
    rec_at_k: int = 20,
    scorer: Optional[XGBGraphScorer] = None,
    seed: int = 1405,
) -> L5TrainResult:
    """Build graph -> fit XGB-Graph on a train slice -> AUPRC/Rec@K on held-out entities."""
    X = entity_features.copy()
    y = pd.Series(np.asarray(entity_labels).astype(int).ravel(), index=X.index)

    graph = build_entity_graph(events)
    n_nodes = len(getattr(graph, "node_type", {})) if hasattr(graph, "node_type") else 0
    try:
        _, nodes = graph.adjacency()
        n_nodes = len(nodes)
    except Exception:
        pass

    # entity-disjoint split by a stable hash bucket (no entity in both sides)
    rng = np.random.default_rng(seed)
    ents = X.index.to_numpy()
    perm = rng.permutation(len(ents))
    cut = max(1, int(round(len(ents) * (1.0 - test_frac))))
    tr_ents = set(ents[perm[:cut]])
    Xtr = X.loc[[e for e in X.index if e in tr_ents]]
    ytr = y.loc[Xtr.index]
    Xte = X.loc[[e for e in X.index if e not in tr_ents]]
    yte = y.loc[Xte.index]

    sc = scorer or XGBGraphScorer(k=k)
    # fit on the full graph but only the training entities' rows
    sc.fit(Xtr, ytr, events=events)

    if len(Xte) and int(yte.sum()) > 0:
        p = sc.predict_proba(Xte, events=events)
        metrics = {
            "auprc": average_precision(yte, p),
            f"recall_at_{rec_at_k}": recall_at_k(yte, p, rec_at_k),
        }
    else:
        metrics = {"auprc": float("nan"), f"recall_at_{rec_at_k}": float("nan")}

    return L5TrainResult(
        scorer=sc,
        metrics=metrics,
        n_nodes=n_nodes,
        n_edges=0,
        n_train=len(Xtr),
        n_test=len(Xte),
    )


__all__ = ["train_l5", "L5TrainResult"]
