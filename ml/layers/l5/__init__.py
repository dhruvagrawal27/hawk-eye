"""L5 Graph layer (ML-6; blueprint §20.5).

Typed entity graph + graph-aware fraud scorers:

* :mod:`graph_build`   — typed entity graph (employees/accounts/beneficiaries/devices/
  vendors), incremental refresh, k-hop aggregates.
* :mod:`xgb_graph`     — :class:`XGBGraphScorer` (DEFAULT) + :class:`RFGraphScorer`
  (k-hop aggregates -> GBDT; GADBench winner; must beat the 0-hop baseline).
* :mod:`graphsage`     — :class:`GraphSAGEScorer` (inductive, torch_geometric).
* :mod:`specialized_gnns` — GAT / HGT / BWGNN / CARE-GNN / PC-GNN (camouflage /
  heterophily-resistant), torch_geometric-guarded.
* :mod:`gnn_explainer` — GNNExplainer-style edge-attribution -> graph ReasonCodes.
* :mod:`gadbench_ablation` — 0->2-hop AUPRC lift harness.

Every module imports even when torch/torch_geometric/LightGBM are absent (heavy
imports live inside methods). The DEFAULT scorer is :class:`XGBGraphScorer`.
"""
from __future__ import annotations

from ml.layers.l5.gadbench_ablation import ablation_0_to_2_hops
from ml.layers.l5.gnn_explainer import explain_node, pyg_gnn_explainer_available
from ml.layers.l5.graph_build import (
    EDGE_TYPES,
    NODE_TYPES,
    EntityGraph,
    build_entity_graph,
    k_hop_aggregates,
)
from ml.layers.l5.graphsage import GraphSAGEScorer
from ml.layers.l5.specialized_gnns import (
    SPECIALIZED_GNNS,
    BWGNNScorer,
    CAREGNNScorer,
    GATScorer,
    HGTScorer,
    PCGNNScorer,
)
from ml.layers.l5.xgb_graph import RFGraphScorer, XGBGraphScorer, graph_design_matrix

# The blueprint DEFAULT L5 scorer.
DEFAULT_SCORER = XGBGraphScorer

__all__ = [
    "EntityGraph",
    "build_entity_graph",
    "k_hop_aggregates",
    "NODE_TYPES",
    "EDGE_TYPES",
    "XGBGraphScorer",
    "RFGraphScorer",
    "graph_design_matrix",
    "DEFAULT_SCORER",
    "GraphSAGEScorer",
    "GATScorer",
    "HGTScorer",
    "BWGNNScorer",
    "CAREGNNScorer",
    "PCGNNScorer",
    "SPECIALIZED_GNNS",
    "ablation_0_to_2_hops",
    "explain_node",
    "pyg_gnn_explainer_available",
]
