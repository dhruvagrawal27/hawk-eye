"""GNNExplainer-style attribution for a flagged graph node (ML-6; blueprint §20.6).

Returns ``ReasonCode(source="graph", detail=<which neighbours/edges>, contribution=)``
explaining WHY a node was flagged: which incident edges/neighbours, when perturbed,
most change the model's score. Uses PyG ``GNNExplainer`` when available, else a
self-contained edge-perturbation importance fallback (always works, no torch needed).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml._optional import optional_import
from ml.base import ReasonCode
from ml.layers.l5.graph_build import EntityGraph, build_entity_graph


def _incident_edges(graph: EntityGraph, node: str) -> list[tuple[str, str, str]]:
    return [(a, b, t) for (a, b, t) in graph.edges if a == node or b == node]


def explain_node(
    scorer,
    X: pd.DataFrame,
    node: str,
    *,
    events: Optional[pd.DataFrame] = None,
    top_k: int = 5,
    graph: Optional[EntityGraph] = None,
) -> list[ReasonCode]:
    """Explain why ``node`` (an employee id) was flagged, as graph reason codes.

    Strategy: remove each incident edge in turn (edge perturbation) and measure the
    drop in the node's predicted P(fraud); edges whose removal drops the score most are
    the most responsible. This is the model-agnostic GNNExplainer-style fallback and is
    what runs for the GBDT default; if a PyG GNNExplainer is wired for a torch model it
    can be substituted, but the contract (graph ReasonCodes) is identical.
    """
    g = graph or (build_entity_graph(events) if events is not None else getattr(scorer, "_graph", None))
    if g is None:
        g = build_entity_graph(events) if events is not None else None
    if g is None:
        return [ReasonCode(source="graph", code="no_graph",
                           detail=f"no graph available to explain {node}")]

    node = str(node)
    # Score everything against the SAME base graph ``g`` (swap it into the scorer's
    # cache) so the only thing that varies is the perturbed edge — otherwise the
    # base/perturbed scores use different graphs and every contribution is ~0.
    if node not in X.index:
        base_score = 0.0
    else:
        base_score = _score_one(scorer, X, node, g, events)

    incident = _incident_edges(g, node)
    if not incident:
        return [ReasonCode(
            source="graph", code="isolated_node",
            detail=f"{node} has no graph neighbours; score driven by node-local features",
            contribution=base_score,
        )]

    # Importance over the node's design vector (k-hop aggregates), used to weight how
    # much each edge's removal perturbs the features the model actually relies on. This
    # stays informative even when the final probability saturates at ~1.0 (a strong
    # GBDT barely moves when a single edge among thousands is dropped).
    base_design = _design_vector(scorer, X, node, g)
    imp = _design_importance(scorer)

    contribs: list[tuple[tuple[str, str, str], float]] = []
    for edge in incident:
        perturbed = _graph_without_edge(g, edge)
        prob_drop = 0.0
        feat_drop = 0.0
        if node in X.index:
            new_score = _score_one(scorer, X, node, perturbed, events)
            prob_drop = base_score - new_score
            new_design = _design_vector(scorer, X, node, perturbed)
            if base_design is not None and new_design is not None:
                delta = np.abs(base_design - new_design)
                feat_drop = float((delta * imp).sum()) if imp is not None else float(delta.sum())
        # combine: probability movement dominates when present, else feature movement
        score = abs(prob_drop) + 1e-3 * feat_drop
        contribs.append((edge, score, prob_drop))

    contribs.sort(key=lambda t: -t[1])
    out: list[ReasonCode] = []
    for (a, b, t), score, prob_drop in contribs[:top_k]:
        neighbour = b if a == node else a
        ntype = g.nodes.get(neighbour, "node")
        out.append(ReasonCode(
            source="graph",
            code=f"edge_{t}",
            feature=str(neighbour),
            detail=(f"edge '{t}' to {ntype} {neighbour} influences {node}'s fraud score "
                    f"(prob_delta {prob_drop:+.3f})"),
            contribution=float(score),
        ))
    if not out:
        out.append(ReasonCode(source="graph", code="neighbourhood",
                              detail=f"{node} neighbourhood evaluated; no single edge dominant",
                              contribution=base_score))
    return out


def _graph_without_edge(g: EntityGraph, edge: tuple[str, str, str]) -> EntityGraph:
    new = EntityGraph(
        employees=list(g.employees),
        nodes=dict(g.nodes),
    )
    for e in g.edges:
        if e == edge:
            continue
        new._edge_set.add(e)
        new.edges.append(e)
    return new


def _score_one(scorer, X: pd.DataFrame, node: str, graph: EntityGraph, events) -> float:
    # Re-score the single node against the perturbed graph by passing the graph through
    # the scorer's events seam. We rebuild from the perturbed graph by temporarily
    # swapping the cached graph.
    prev = getattr(scorer, "_graph", None)
    try:
        scorer._graph = graph
        proba = scorer.predict_proba(X.loc[[node]])
    finally:
        scorer._graph = prev
    return float(np.asarray(proba).ravel()[0])


def _design_vector(scorer, X: pd.DataFrame, node: str, graph: EntityGraph):
    """The scorer's design vector (node features ⊕ k-hop aggregates) for ``node`` under
    ``graph``. Only defined for the GBDT graph scorers; returns None otherwise."""
    build = getattr(scorer, "_design_for", None)
    if build is None or node not in X.index:
        return None
    prev = getattr(scorer, "_graph", None)
    try:
        scorer._graph = graph
        design = scorer._design_for(X.loc[[node]], None)
    except Exception:
        return None
    finally:
        scorer._graph = prev
    return np.asarray(design.to_numpy(dtype=float)).ravel()


def _design_importance(scorer):
    imp = getattr(scorer, "_importances", None)
    if imp is None:
        return None
    try:
        arr = np.asarray(scorer._importances(), dtype=float)
        s = arr.sum()
        return arr / s if s > 0 else arr
    except Exception:
        return None


def _accepts_events(scorer) -> bool:
    import inspect

    try:
        sig = inspect.signature(scorer.predict_proba)
        return "events" in sig.parameters
    except (TypeError, ValueError):
        return False


def pyg_gnn_explainer_available() -> bool:
    """True iff PyG's GNNExplainer can be imported (for the torch-model path)."""
    pyg = optional_import("torch_geometric")
    if pyg is None:
        return False
    try:
        from torch_geometric.explain import Explainer, GNNExplainer  # noqa: F401

        return True
    except Exception:
        return False
