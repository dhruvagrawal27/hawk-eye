"""L5 camouflage / heterophily-resistant GNNs (ML-6; blueprint §20.5).

Compact, trainable implementations of the GAD specialists the blueprint lists:

* :class:`GATScorer`   — Graph Attention Network (attention over neighbours).
* :class:`HGTScorer`   — Heterogeneous-graph-style transformer conv (typed relations).
* :class:`BWGNNScorer` — Beta-Wavelet GNN flavour (heterophily-resistant; band-pass
  message passing approximated with a high-pass + low-pass mix).
* :class:`CAREGNNScorer` — CARE-GNN flavour (camouflage-resistant neighbour selection
  via a learned similarity gate).
* :class:`PCGNNScorer` — PC-GNN flavour (label-balanced neighbour pick/choose).

They share a small :class:`_BaseSpecializedGNN` (graph build, PyG plumbing, training
loop, predict, reason codes). Each is constructible and trainable on a tiny graph.
All torch_geometric-guarded: heavy imports live inside methods; ``fit`` requires the
dep. The module ALWAYS imports.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np
import pandas as pd

# See ml.layers.l5.graphsage for why: avoid the macOS dual-OpenMP segfault in the
# torch_geometric message-passing kernels. Idempotent; harmless where it doesn't apply.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from ml._optional import require
from ml.base import BaseScorer, ReasonCode
from ml.layers.l5.graph_build import EntityGraph, build_entity_graph
from ml.layers.l5.graphsage import _identity_graph
from ml.layers.l5.xgb_graph import _align_node_features


class _BaseSpecializedGNN(BaseScorer):
    """Common plumbing for the specialized GAD GNNs."""

    layer = "L5"
    kind = "base"

    def __init__(
        self,
        *,
        hidden: int = 64,
        epochs: int = 30,
        lr: float = 0.01,
        dropout: float = 0.5,
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=f"l5-{self.kind}", version=version)
        self.hidden = int(hidden)
        self.epochs = int(epochs)
        self.lr = float(lr)
        self.dropout = float(dropout)
        self._model: Any = None
        self._graph: Optional[EntityGraph] = None

    # subclasses build the torch module given an input dim
    def _build_net(self, in_dim: int):  # pragma: no cover - overridden
        raise NotImplementedError

    def _to_tensors(self, X: pd.DataFrame, graph: EntityGraph, y):
        import torch

        node_feat, A = _align_node_features(X, graph)
        nodes = [str(i) for i in node_feat.index]
        idx = {n: i for i, n in enumerate(nodes)}
        src, dst = np.nonzero(A)
        if src.size == 0:
            src = np.arange(len(nodes))
            dst = np.arange(len(nodes))
        edge_index = torch.tensor(np.vstack([src, dst]), dtype=torch.long)
        feats = torch.tensor(node_feat.to_numpy(dtype=float), dtype=torch.float32)
        mu = feats.mean(0, keepdim=True)
        sd = feats.std(0, keepdim=True)
        sd[sd == 0] = 1.0
        feats = (feats - mu) / sd
        emp_mask = torch.tensor([n in X.index for n in nodes], dtype=torch.bool)
        labels = None
        if y is not None:
            ys = pd.Series(np.asarray(y).astype(int), index=X.index)
            labels = torch.tensor([int(ys.get(n, 0)) for n in nodes], dtype=torch.long)
        return feats, edge_index, emp_mask, labels, nodes, idx

    def fit(  # type: ignore[override]  # intentional: graph fit adds events= and requires y
        self, X: pd.DataFrame, y, events: Optional[pd.DataFrame] = None
    ) -> "_BaseSpecializedGNN":
        require("torch_geometric")
        import torch

        self._graph = (
            build_entity_graph(events)
            if events is not None
            else (self._graph or _identity_graph(X))
        )
        feats, edge_index, emp_mask, labels, _, _ = self._to_tensors(
            X, self._graph, np.asarray(y)
        )
        net = self._build_net(feats.shape[1])
        net.train()
        y_emp = labels[emp_mask]
        n_pos = int((y_emp == 1).sum())
        n_neg = int((y_emp == 0).sum())
        w = torch.tensor([1.0, max(1.0, n_neg / max(1, n_pos))], dtype=torch.float32)
        opt = torch.optim.Adam(net.parameters(), lr=self.lr, weight_decay=5e-4)
        loss_fn = torch.nn.CrossEntropyLoss(weight=w)
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

    def predict_proba(
        self, X: pd.DataFrame, events: Optional[pd.DataFrame] = None
    ) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise RuntimeError("scorer is not fitted")
        import torch

        graph = (
            build_entity_graph(events)
            if events is not None
            else (self._graph or _identity_graph(X))
        )
        feats, edge_index, _, _, nodes, idx = self._to_tensors(X, graph, None)
        with torch.no_grad():
            logits = self._model(feats, edge_index)
            proba = torch.softmax(logits, dim=1)[:, 1].cpu().numpy()
        out = np.array(
            [float(proba[idx[str(e)]]) if str(e) in idx else 0.0 for e in X.index]
        )
        return np.clip(out, 0.0, 1.0)

    def reason_codes(
        self, X: pd.DataFrame, top_k: int = 5, events: Optional[pd.DataFrame] = None
    ) -> list[list[ReasonCode]]:
        graph = (
            build_entity_graph(events)
            if events is not None
            else (self._graph or _identity_graph(X))
        )
        A, nodes = graph.adjacency()
        idx = {n: i for i, n in enumerate(nodes)}
        deg = A.sum(axis=1)
        out = []
        for e in X.index:
            i = idx.get(str(e))
            d = float(deg[i]) if i is not None else 0.0
            out.append(
                [
                    ReasonCode(
                        source="attention" if self.kind in ("gat", "hgt") else "graph",
                        code=f"{self.kind}_neighbourhood",
                        detail=f"{self.kind.upper()} aggregated {int(d)} neighbours of {e}",
                        contribution=d,
                    )
                ]
            )
        return out


class GATScorer(_BaseSpecializedGNN):
    kind = "gat"

    def _build_net(self, in_dim: int):
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import GATConv

        hidden, dropout = self.hidden, self.dropout

        class _GAT(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.c1 = GATConv(in_dim, hidden, heads=2, concat=True, dropout=dropout)
                self.c2 = GATConv(
                    hidden * 2, hidden, heads=1, concat=False, dropout=dropout
                )
                self.lin = torch.nn.Linear(hidden, 2)

            def forward(self, x, ei):
                x = F.elu(self.c1(x, ei))
                x = F.dropout(x, p=dropout, training=self.training)
                x = F.elu(self.c2(x, ei))
                return self.lin(x)

        return _GAT()


class HGTScorer(_BaseSpecializedGNN):
    """Heterogeneous-transformer flavour. Uses TransformerConv (attention) as a compact
    homogeneous stand-in for HGT on the (already typed) entity graph."""

    kind = "hgt"

    def _build_net(self, in_dim: int):
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import TransformerConv

        hidden, dropout = self.hidden, self.dropout

        class _HGT(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.c1 = TransformerConv(
                    in_dim, hidden, heads=2, concat=False, dropout=dropout
                )
                self.c2 = TransformerConv(
                    hidden, hidden, heads=1, concat=False, dropout=dropout
                )
                self.lin = torch.nn.Linear(hidden, 2)

            def forward(self, x, ei):
                x = F.elu(self.c1(x, ei))
                x = F.dropout(x, p=dropout, training=self.training)
                x = F.elu(self.c2(x, ei))
                return self.lin(x)

        return _HGT()


class BWGNNScorer(_BaseSpecializedGNN):
    """Beta-Wavelet GNN flavour: mix a low-pass (mean) and high-pass (I - mean) signal so
    heterophilous fraud (camouflaged among benign neighbours) survives aggregation."""

    kind = "bwgnn"

    def _build_net(self, in_dim: int):
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import SGConv

        hidden, dropout = self.hidden, self.dropout

        class _BW(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.low = SGConv(in_dim, hidden, K=2)  # low-pass band
                self.lin_self = torch.nn.Linear(in_dim, hidden)  # high-pass (self) band
                self.lin = torch.nn.Linear(hidden * 2, 2)

            def forward(self, x, ei):
                lo = F.relu(self.low(x, ei))  # smoothed neighbourhood
                hi = F.relu(self.lin_self(x))  # node-local (band-pass residual)
                h = torch.cat([lo, hi], dim=1)
                h = F.dropout(h, p=dropout, training=self.training)
                return self.lin(h)

        return _BW()


class CAREGNNScorer(_BaseSpecializedGNN):
    """CARE-GNN flavour: a learned similarity gate down-weights camouflaging neighbours
    (fraudsters connecting to many benign nodes to dilute the signal)."""

    kind = "care_gnn"

    def _build_net(self, in_dim: int):
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import SAGEConv

        hidden, dropout = self.hidden, self.dropout

        class _CARE(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.proj = torch.nn.Linear(in_dim, hidden)
                self.conv = SAGEConv(hidden, hidden, aggr="mean")
                self.gate = torch.nn.Linear(hidden, hidden)  # similarity-aware gate
                self.lin = torch.nn.Linear(hidden, 2)

            def forward(self, x, ei):
                h = F.relu(self.proj(x))
                agg = F.relu(self.conv(h, ei))
                g = torch.sigmoid(
                    self.gate(h)
                )  # keep node-local where neighbours look dissimilar
                h = g * h + (1 - g) * agg
                h = F.dropout(h, p=dropout, training=self.training)
                return self.lin(h)

        return _CARE()


class PCGNNScorer(_BaseSpecializedGNN):
    """PC-GNN flavour: label-balanced pick-and-choose. Approximated by oversampling the
    minority class in the supervised loss (choose step) with a residual aggregator (pick).
    """

    kind = "pc_gnn"

    def _build_net(self, in_dim: int):
        import torch
        import torch.nn.functional as F
        from torch_geometric.nn import SAGEConv

        hidden, dropout = self.hidden, self.dropout

        class _PC(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.c1 = SAGEConv(in_dim, hidden, aggr="mean")
                self.res = torch.nn.Linear(in_dim, hidden)
                self.lin = torch.nn.Linear(hidden, 2)

            def forward(self, x, ei):
                h = F.relu(self.c1(x, ei)) + F.relu(
                    self.res(x)
                )  # pick (neighbour) + residual
                h = F.dropout(h, p=dropout, training=self.training)
                return self.lin(h)

        return _PC()


SPECIALIZED_GNNS = {
    "gat": GATScorer,
    "hgt": HGTScorer,
    "bwgnn": BWGNNScorer,
    "care_gnn": CAREGNNScorer,
    "pc_gnn": PCGNNScorer,
}
