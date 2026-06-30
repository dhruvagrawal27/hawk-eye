"""Tests for the L5 GRAPH layer (ML-6; blueprint Part 20.5).

Validates the typed entity graph + graph-aware fraud scorers:

* a TYPED entity graph builds from L0 events (employee/account/beneficiary/device/
  vendor nodes; transaction/access/shared-attribute typed edges) and
  ``incremental_refresh`` folds in new events idempotently;
* :class:`XGBGraphScorer` — the L5 DEFAULT — trains on k-hop aggregates, scores in
  [0,1], and surfaces graph reason codes (``source="graph"``);
* the GADBench 0->2-hop ablation shows the aggregation lift: AUPRC at 2 hops beats
  AUPRC at 0 hops on a homophilous graph where the class signal lives in the
  NEIGHBOURHOOD (per-node features are buried in noise — the canonical setup that
  makes XGB-Graph the GADBench winner);
* :class:`GraphSAGEScorer` trains on a tiny graph for a few epochs (skipped cleanly
  if torch_geometric is absent);
* :func:`explain_node` (GNNExplainer-style) yields graph ``ReasonCode``s for a
  flagged node.

The DEFAULT (XGB-Graph) path needs NO torch_geometric. Run:
    .mlvenv/bin/python -m pytest tests/ml/test_l5.py -q
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# OpenMP guard. torch ships its own libomp and so do lightgbm/sklearn/woodwork;
# on macOS loading both can SIGSEGV inside torch_geometric's message-passing
# kernels. KMP_DUPLICATE_LIB_OK lets the second runtime load (libomp reads it
# lazily, so setting it before the first GNN forward pass is enough). The L5 GNN
# modules set the same defaults; this is belt-and-suspenders for import ordering.
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd
import pytest

from ml._optional import HAS_TORCH_GEOMETRIC
from ml.base import BaseScorer, ReasonCode
from ml.layers.l5 import (
    DEFAULT_SCORER,
    EDGE_TYPES,
    NODE_TYPES,
    EntityGraph,
    GraphSAGEScorer,
    XGBGraphScorer,
    ablation_0_to_2_hops,
    build_entity_graph,
    explain_node,
    k_hop_aggregates,
    pyg_gnn_explainer_available,
)


# --------------------------------------------------------------------------- #
# fixtures                                                                    #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def synth():
    """Real DATA-sim feature source (entity features + 0/1 labels + raw events)."""
    from ml.adapters import SyntheticFeatureSource

    src = SyntheticFeatureSource(n_employees=40, n_days=6, seed=1405)
    ev = src.events()
    ef = src.entity_features()
    el = src.entity_labels()
    assert int(el.sum()) >= 3, "need positives to train/score on"
    return ev, ef, el


@pytest.fixture(scope="module")
def typed_events():
    """A hand-built event batch that exercises ALL node types (incl. vendor) and
    every non-beneficiary edge type, plus a 3-way shared-device/account ring."""
    rows = [
        # employee -> account (application => transaction), device (access), beneficiary
        {
            "actor.employee_id": "EMP-1",
            "object.account_id": "ACC-1",
            "context.device": "DEV-1",
            "object.beneficiary_id": "BEN-1",
            "context.layer": "application",
            "action.verb": "approve_payment",
            "linkage.customer_account": "ACC-9",
        },
        # employee -> database (=> access edge); VEND- beneficiary types as a vendor node
        {
            "actor.employee_id": "EMP-2",
            "object.account_id": "ACC-1",
            "context.device": "DEV-1",
            "object.beneficiary_id": "VEND-77",
            "context.layer": "database",
            "action.verb": "db_select",
            "linkage.customer_account": "ACC-1",
        },
        # third employee shares DEV-1 and ACC-1 with the first two (collusion ring)
        {
            "actor.employee_id": "EMP-3",
            "object.account_id": "ACC-1",
            "context.device": "DEV-1",
            "object.beneficiary_id": "",
            "context.layer": "application",
            "action.verb": "login",
            "linkage.customer_account": "",
        },
    ]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 1. typed entity graph + incremental refresh                                 #
# --------------------------------------------------------------------------- #
def test_typed_graph_builds_all_node_and_edge_types(typed_events):
    g = build_entity_graph(typed_events)

    # every node carries a valid type; all five types appear at least once.
    assert set(g.nodes.values()) <= set(NODE_TYPES)
    present_node_types = set(g.nodes.values())
    for nt in ("employee", "account", "beneficiary", "device", "vendor"):
        assert nt in present_node_types, f"missing node type {nt}"
    # VEND- beneficiary is typed as a vendor, plain BEN- as a beneficiary.
    assert g.nodes["VEND-77"] == "vendor"
    assert g.nodes["BEN-1"] == "beneficiary"

    # typed edges: transaction + access (from layer) and shared-attribute collusion edges.
    edge_types = {t for _, _, t in g.edges}
    assert edge_types <= set(EDGE_TYPES)
    assert "transaction" in edge_types  # application-layer account / beneficiary links
    assert "access" in edge_types  # database-layer + device links
    # the three employees share DEV-1 and ACC-1 -> shared-attribute (collusion) edges.
    assert "shared_device" in edge_types
    assert "shared_account" in edge_types

    # employees are the primary entities, tracked in insertion order.
    assert g.employees == ["EMP-1", "EMP-2", "EMP-3"]
    assert g.n_nodes == len(g.nodes) and g.n_edges == len(g.edges) > 0


def test_incremental_refresh_is_idempotent_then_grows(typed_events):
    g = build_entity_graph(typed_events)
    n_nodes0, n_edges0 = g.n_nodes, g.n_edges

    # re-feeding identical events must NOT double-count (dedup via internal edge set).
    g.incremental_refresh(typed_events)
    assert g.n_nodes == n_nodes0
    assert g.n_edges == n_edges0

    # a genuinely new event folds in new nodes + edges (hourly cadence).
    new = pd.DataFrame(
        [
            {
                "actor.employee_id": "EMP-4",
                "object.account_id": "ACC-2",
                "context.device": "DEV-2",
                "object.beneficiary_id": "BEN-2",
                "context.layer": "application",
                "action.verb": "approve_payment",
                "linkage.customer_account": "",
            },
        ]
    )
    g.incremental_refresh(new)
    assert "EMP-4" in g.nodes and g.nodes["EMP-4"] == "employee"
    assert "EMP-4" in g.employees
    assert g.n_nodes > n_nodes0
    assert g.n_edges > n_edges0


def test_adjacency_and_k_hop_aggregates_shapes(synth):
    ev, ef, _ = synth
    g = build_entity_graph(ev)
    A, nodes = g.adjacency()
    assert A.shape == (len(nodes), len(nodes))
    assert np.array_equal(A, A.T), "adjacency must be symmetric (undirected graph)"

    # restrict to the employee rows aligned with their entity features.
    A_full, full_nodes = g.adjacency()
    idx = {n: i for i, n in enumerate(full_nodes)}
    emp_ix = [idx[e] for e in g.employees]
    A_emp = A_full[np.ix_(emp_ix, emp_ix)]
    X_emp = ef.loc[g.employees]

    agg0 = k_hop_aggregates(X_emp, A_emp, k=0, graph=g)
    agg2 = k_hop_aggregates(X_emp, A_emp, k=2, graph=g)
    # 0-hop carries structural columns only; 2-hop adds neighbour mean/sum/max rings.
    assert {"graph_degree", "graph_centrality", "graph_shared_attr_count"} <= set(
        agg0.columns
    )
    assert agg2.shape[1] > agg0.shape[1]
    assert len(agg2) == len(X_emp)
    assert np.isfinite(agg2.to_numpy()).all()


# --------------------------------------------------------------------------- #
# 2. XGB-Graph DEFAULT scorer                                                 #
# --------------------------------------------------------------------------- #
def test_xgb_graph_is_the_default_scorer():
    assert DEFAULT_SCORER is XGBGraphScorer
    assert issubclass(XGBGraphScorer, BaseScorer)


def test_xgb_graph_trains_scores_and_emits_graph_reason_codes(synth):
    ev, ef, el = synth
    scorer = XGBGraphScorer(k=2)
    scorer.fit(ef, el.to_numpy(), events=ev)

    assert scorer.is_fitted
    assert scorer.layer == "L5"
    # the booster degrades gracefully but is REAL (lightgbm/xgboost/sklearn-histgb).
    assert scorer._impl in ("lightgbm", "xgboost", "sklearn-histgb")
    # design matrix actually used k-hop graph aggregates (nbr_*) not just node features.
    assert any(c.startswith("nbr_") for c in scorer._columns)

    proba = scorer.predict_proba(ef)
    assert proba.shape == (len(ef),)
    assert np.all((proba >= 0.0) & (proba <= 1.0)), "predict_proba must be in [0,1]"
    assert np.isfinite(proba).all()

    # fraud employees should, on average, score above benign ones (sanity, not strict).
    y = el.to_numpy().astype(bool)
    assert proba[y].mean() > proba[~y].mean()

    # reason codes: right shape + at least one graph-sourced aggregate fired somewhere.
    rcs = scorer.reason_codes(ef, top_k=5)
    assert len(rcs) == len(ef)
    assert all(isinstance(c, ReasonCode) for row in rcs for c in row)
    all_codes = [c for row in rcs for c in row]
    assert all(c.source in ("graph", "shap") for c in all_codes)
    assert any(
        c.source == "graph" for c in all_codes
    ), "expected k-hop graph reason codes"


# --------------------------------------------------------------------------- #
# 3. GADBench 0->2-hop ablation lift                                          #
# --------------------------------------------------------------------------- #
def _homophily_ring(seed: int = 11):
    """A homophilous graph where the class signal lives in the NEIGHBOURHOOD.

    Both classes are wired with identical degree (so degree/centrality cannot cheat
    at 0 hops), and each node's OWN feature is the latent class mean buried under
    heavy noise — individually unreliable, but recoverable by averaging neighbour
    features. This is the canonical GADBench setup where k-hop aggregation lifts AUPRC.
    """
    rng = np.random.default_rng(seed)
    n_f = n_b = 60
    n = n_f + n_b
    y = np.array([1] * n_f + [0] * n_b)
    emps = [f"EMP-{i:04d}" for i in range(n)]
    g = EntityGraph(employees=list(emps), nodes={e: "employee" for e in emps})

    def wire(group, etype, deg=4):
        for u in group:
            partners = rng.choice([v for v in group if v != u], size=deg, replace=False)
            for v in partners:
                g.add_edge(emps[u], emps[v], etype)

    # identical wiring (same degree, same edge type) within each class -> homophily,
    # non-discriminative structure.
    wire(range(n_f), "shared_account")
    wire(range(n_f, n), "shared_account")

    A, _ = g.adjacency(emps)
    latent = np.where(y == 1, 1.0, -1.0)
    own = latent + rng.normal(0.0, 4.0, size=n)  # heavy noise: 0-hop barely separates
    X = pd.DataFrame({"signal": own}, index=pd.Index(emps, name="employee_id"))
    X["noise0"] = rng.normal(0, 1, n)  # a pure-noise column for good measure
    return X, A, y, g


def test_gadbench_0_to_2_hop_ablation_lift():
    X, A, y, g = _homophily_ring(seed=11)
    rows = ablation_0_to_2_hops(X, A, y, graph=g, seed=1405, test_frac=0.4)

    # one row per hop level, sorted 0,1,2; AUPRC reported per hop.
    assert [r["hops"] for r in rows] == [0, 1, 2]
    assert all(0.0 <= r["auprc"] <= 1.0 for r in rows)
    # adding hops grows the feature count (neighbour aggregates appended).
    assert rows[0]["n_features"] < rows[1]["n_features"] < rows[2]["n_features"]

    auprc_0 = rows[0]["auprc"]
    auprc_2 = rows[-1]["auprc"]
    # GADBench aggregation lift: 2-hop AUPRC >= 0-hop (here a strict, large win because
    # the class signal is neighbourhood-borne). The small tolerance documents that on a
    # tiny toy graph the strict win is not guaranteed every seed; the lift is real here.
    assert auprc_2 >= auprc_0 - 1e-9, f"2-hop AUPRC {auprc_2:.3f} < 0-hop {auprc_0:.3f}"
    # this constructed graph is deliberately neighbourhood-driven, so we expect a clear win.
    assert (
        auprc_2 > auprc_0 + 0.1
    ), f"expected a clear aggregation lift, got 0-hop={auprc_0:.3f} 2-hop={auprc_2:.3f}"


# --------------------------------------------------------------------------- #
# 4. GraphSAGE (torch_geometric path)                                         #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAS_TORCH_GEOMETRIC, reason="torch_geometric not installed")
def test_graphsage_trains_on_tiny_graph(synth):
    ev, ef, el = synth
    # tiny + few epochs to keep it fast (<~few seconds).
    sage = GraphSAGEScorer(hidden=32, epochs=15, lr=0.01)
    sage.fit(ef, el.to_numpy(), events=ev)
    assert sage.is_fitted
    assert sage.layer == "L5"

    proba = sage.predict_proba(ef)
    assert proba.shape == (len(ef),)
    assert np.all((proba >= 0.0) & (proba <= 1.0))
    assert np.isfinite(proba).all()
    # the model actually learned *something* (not a constant output).
    assert proba.std() > 0.0

    rcs = sage.reason_codes(ef)
    assert len(rcs) == len(ef)
    assert all(c.source == "graph" for row in rcs for c in row)


# --------------------------------------------------------------------------- #
# 5. GNNExplainer-style graph reason codes for a flagged node                 #
# --------------------------------------------------------------------------- #
def test_gnn_explainer_yields_graph_reason_codes_for_flagged_node(synth):
    ev, ef, el = synth
    scorer = XGBGraphScorer(k=2)
    scorer.fit(ef, el.to_numpy(), events=ev)

    proba = scorer.predict_proba(ef)
    flagged = str(ef.index[int(np.argmax(proba))])  # the highest-scoring employee

    codes = explain_node(scorer, ef, flagged, events=ev, top_k=5)
    assert len(codes) >= 1
    assert all(isinstance(c, ReasonCode) for c in codes)
    # the contract: graph-sourced provenance explaining the flagged node.
    assert all(c.source == "graph" for c in codes)
    # at least one code references a concrete incident edge/neighbour (not just a stub).
    assert any((c.code or "").startswith("edge_") or c.feature for c in codes)


def test_pyg_gnn_explainer_availability_flag_is_boolean():
    # the torch-model GNNExplainer path is optional; the helper must answer cleanly.
    assert isinstance(pyg_gnn_explainer_available(), bool)
