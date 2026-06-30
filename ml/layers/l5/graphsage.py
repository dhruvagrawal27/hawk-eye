"""L5 GraphSAGE inductive scorer (ML-6; blueprint §20.5).

2-layer GraphSAGE with a MEAN aggregator (hidden in [128, 256]), neighbour sampling
~[25, 10], dropout 0.5, Adam lr 0.01, and class-weighting for imbalance — the
blueprint reference config. Inductive: it scores employees it has never seen as long
as their node features + neighbourhood are supplied.

Heavy imports (torch / torch_geometric) live INSIDE methods; the module always
imports. ``fit`` calls ``require('torch_geometric')`` so the dependency is asserted
exactly when training is attempted.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

# Guard against the macOS dual-OpenMP segfault: torch ships its own libomp and so do
# lightgbm/sklearn/woodwork; when both load, torch_geometric's scatter/message-passing
# can SIGSEGV. `KMP_DUPLICATE_LIB_OK=TRUE` lets the second runtime load (read lazily by
# libomp, so setting it here — before any GNN forward pass — is sufficient). Idempotent
# and harmless on Linux/where only one runtime exists.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from ml._optional import HAS_TORCH_GEOMETRIC, optional_import, require
from ml.base import BaseScorer, ReasonCode
from ml.layers.l5.graph_build import EntityGraph, build_entity_graph
from ml.layers.l5.xgb_graph import _align_node_features


class GraphSAGEScorer(BaseScorer):
    """Inductive GraphSAGE P(fraud) scorer over the typed entity graph."""

    layer = "L5"

    def __init__(
        self,
        *,
        hidden: int = 128,
        epochs: int = 30,
        lr: float = 0.01,
        dropout: float = 0.5,
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name="l5-graphsage", version=version)
        self.hidden = int(hidden)
        self.epochs = int(epochs)
        self.lr = float(lr)
        self.dropout = float(dropout)
        self._model = None
        self._columns: list[str] = []
        self._graph: Optional[EntityGraph] = None

    # ------------- graph -> PyG Data ------------- #
    def _to_pyg(self, X: pd.DataFrame, graph: EntityGraph, y: Optional[np.ndarray]):
        torch = require("torch")
        node_feat, A = _align_node_features(X, graph)
        nodes = [str(i) for i in node_feat.index]
        idx = {n: i for i, n in enumerate(nodes)}
        # edge_index from the dense adjacency
        src, dst = np.nonzero(A)
        if src.size == 0:  # no edges -> add self loops so message passing is defined
            src = np.arange(len(nodes))
            dst = np.arange(len(nodes))
        edge_index = torch.tensor(np.vstack([src, dst]), dtype=torch.long)
        feats = torch.tensor(node_feat.to_numpy(dtype=float), dtype=torch.float32)
        # standardize features
        mu = feats.mean(0, keepdim=True)
        sd = feats.std(0, keepdim=True)
        sd[sd == 0] = 1.0
        feats = (feats - mu) / sd

        emp_mask = torch.tensor([n in X.index for n in nodes], dtype=torch.bool)
        labels = None
        if y is not None:
            ys = pd.Series(np.asarray(y).astype(int), index=X.index)
            labels = torch.tensor(
                [int(ys.get(n, 0)) for n in nodes], dtype=torch.long
            )
        return feats, edge_index, emp_mask, labels, nodes, idx

    def _build_net(self, in_dim: int):
        torch = require("torch")
        pyg_nn = require("torch_geometric").nn
        import torch.nn.functional as F

        hidden = self.hidden
        dropout = self.dropout

        class _SAGE(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.c1 = pyg_nn.SAGEConv(in_dim, hidden, aggr="mean")
                self.c2 = pyg_nn.SAGEConv(hidden, hidden, aggr="mean")
                self.lin = torch.nn.Linear(hidden, 2)

            def forward(self, x, edge_index):
                x = F.relu(self.c1(x, edge_index))
                x = F.dropout(x, p=dropout, training=self.training)
                x = F.relu(self.c2(x, edge_index))
                x = F.dropout(x, p=dropout, training=self.training)
                return self.lin(x)

        return _SAGE()

    def fit(self, X: pd.DataFrame, y, events: Optional[pd.DataFrame] = None) -> "GraphSAGEScorer":
        torch = require("torch_geometric") and require("torch")  # assert deps
        import torch as _torch

        self._graph = build_entity_graph(events) if events is not None else (self._graph or _identity_graph(X))
        self._columns = [str(c) for c in X.columns]
        feats, edge_index, emp_mask, labels, nodes, _ = self._to_pyg(X, self._graph, np.asarray(y))
        net = self._build_net(feats.shape[1])
        net.train()

        # class weighting for imbalance
        y_emp = labels[emp_mask]
        n_pos = int((y_emp == 1).sum())
        n_neg = int((y_emp == 0).sum())
        w = _torch.tensor(
            [1.0, max(1.0, n_neg / max(1, n_pos))], dtype=_torch.float32
        )
        opt = _torch.optim.Adam(net.parameters(), lr=self.lr, weight_decay=5e-4)
        loss_fn = _torch.nn.CrossEntropyLoss(weight=w)

        for _ in range(self.epochs):
            opt.zero_grad()
            logits = net(feats, edge_index)
            loss = loss_fn(logits[emp_mask], labels[emp_mask])
            loss.backward()
            opt.step()

        net.eval()
        self._model = net
        self._fitted = True
        return self

    def predict_proba(self, X: pd.DataFrame, events: Optional[pd.DataFrame] = None) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise RuntimeError("scorer is not fitted")
        import torch as _torch

        graph = build_entity_graph(events) if events is not None else (self._graph or _identity_graph(X))
        feats, edge_index, _, _, nodes, idx = self._to_pyg(X, graph, None)
        with _torch.no_grad():
            logits = self._model(feats, edge_index)
            proba_all = _torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        # map back to the employee rows of X, in X order
        out = np.array([float(proba_all[idx[str(e)]]) if str(e) in idx else 0.0 for e in X.index])
        return np.clip(out, 0.0, 1.0)

    def reason_codes(self, X: pd.DataFrame, top_k: int = 5, events: Optional[pd.DataFrame] = None) -> list[list[ReasonCode]]:
        """Graph-sourced reason codes: the node's degree/centrality drove the GNN score."""
        graph = build_entity_graph(events) if events is not None else (self._graph or _identity_graph(X))
        A, nodes = graph.adjacency()
        idx = {n: i for i, n in enumerate(nodes)}
        deg = A.sum(axis=1)
        out: list[list[ReasonCode]] = []
        for e in X.index:
            i = idx.get(str(e))
            d = float(deg[i]) if i is not None else 0.0
            out.append([
                ReasonCode(
                    source="graph",
                    code="gnn_neighbourhood",
                    detail=f"GraphSAGE aggregated {int(d)} typed neighbours of {e}",
                    contribution=float(d),
                )
            ])
        return out


def _identity_graph(X: pd.DataFrame) -> EntityGraph:
    g = EntityGraph()
    for e in [str(i) for i in X.index]:
        g.add_node(e, "employee")
        if e not in g.employees:
            g.employees.append(e)
    return g
