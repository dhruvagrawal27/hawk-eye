"""L5 typed entity graph construction + k-hop aggregation (ML-6; blueprint §20.5).

Builds a TYPED entity graph from flattened L0 events:

* nodes   = employees, accounts, beneficiaries, devices, vendors
* edges   = transactions / access / shared-attribute links (typed)

The PRIMARY entity is the employee (the node set is aligned to the per-employee
``entity_features`` index so the GBDT/GNN scorers can attach node features 1:1).

Two public surfaces:

* :class:`EntityGraph` — the typed multi-relational graph with
  :meth:`incremental_refresh` for online/hourly cadence (blueprint §18 "L5 hourly").
* :func:`k_hop_aggregates` — per-node mean/sum/max of neighbour features +
  degree + centrality + shared-attribute counts, for k in {1, 2}.

``networkx`` is used when present (centrality), else a pure-numpy adjacency path.
The module ALWAYS imports — heavy imports stay inside methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ml._optional import optional_import

# Node types in the typed graph.
NODE_TYPES = ("employee", "account", "beneficiary", "device", "vendor")
# Edge (relation) types.
EDGE_TYPES = ("transaction", "access", "shared_device", "shared_account", "shared_beneficiary")

EMP = "actor.employee_id"


def _s(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col in df.columns:
        return df[col].astype(str).fillna("")
    return pd.Series(default, index=df.index, dtype=object)


@dataclass
class EntityGraph:
    """A typed multi-relational entity graph built from L0 events.

    ``employees`` is the ordered list of employee node ids (the primary entities,
    aligned to ``entity_features`` index). ``nodes`` maps node-id -> node-type.
    ``edges`` is a list of (src, dst, edge_type) triples (undirected, deduped).
    """

    employees: list[str] = field(default_factory=list)
    nodes: dict[str, str] = field(default_factory=dict)  # node_id -> node_type
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    _edge_set: set[tuple[str, str, str]] = field(default_factory=set, repr=False)

    # ---------------- construction ---------------- #
    def add_node(self, node_id: str, node_type: str) -> None:
        if not node_id:
            return
        if node_type not in NODE_TYPES:
            raise ValueError(f"node_type must be one of {NODE_TYPES}, got {node_type!r}")
        # Employees keep their type; never downgrade an employee node.
        if node_id not in self.nodes or self.nodes[node_id] == node_type:
            self.nodes.setdefault(node_id, node_type)

    def add_edge(self, src: str, dst: str, edge_type: str) -> None:
        if not src or not dst or src == dst:
            return
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"edge_type must be one of {EDGE_TYPES}, got {edge_type!r}")
        a, b = (src, dst) if src <= dst else (dst, src)
        key = (a, b, edge_type)
        if key not in self._edge_set:
            self._edge_set.add(key)
            self.edges.append(key)

    def ingest(self, events: pd.DataFrame) -> "EntityGraph":
        """Add the nodes/edges implied by a batch of flattened L0 events."""
        if events is None or len(events) == 0:
            return self
        df = events.reset_index(drop=True)
        emp = _s(df, EMP)
        acct = _s(df, "object.account_id")
        bene = _s(df, "object.beneficiary_id")
        dev = _s(df, "context.device")
        cust = _s(df, "linkage.customer_account")
        verb = _s(df, "action.verb")
        layer = _s(df, "context.layer")

        for i in range(len(df)):
            e = emp.iat[i]
            if not e:
                continue
            self.add_node(e, "employee")
            if e not in self.employees:
                self.employees.append(e)

            a = acct.iat[i]
            if a:
                self.add_node(a, "account")
                self.add_edge(e, a, "access" if layer.iat[i] == "database" else "transaction")

            b = bene.iat[i]
            if b:
                # A beneficiary that looks like a vendor payout is typed as a vendor.
                ntype = "vendor" if str(b).upper().startswith(("VEND", "VND", "VEN-")) else "beneficiary"
                self.add_node(b, ntype)
                self.add_edge(e, b, "transaction")

            d = dev.iat[i]
            if d:
                self.add_node(d, "device")
                self.add_edge(e, d, "access")

            c = cust.iat[i]
            if c and c != a:
                self.add_node(c, "account")
                self.add_edge(e, c, "access" if verb.iat[i].startswith("db_") else "transaction")

        # Shared-attribute edges: employees that share a device / account / beneficiary
        # are linked (typed) — the classic collusion / mule signal.
        self._add_shared_edges(df, dev, "device", "shared_device")
        self._add_shared_edges(df, acct, "account", "shared_account")
        self._add_shared_edges(df, bene, "beneficiary", "shared_beneficiary")
        return self

    def _add_shared_edges(self, df: pd.DataFrame, attr: pd.Series, _kind: str, edge_type: str) -> None:
        emp = _s(df, EMP)
        tmp = pd.DataFrame({"emp": emp.values, "attr": attr.values})
        tmp = tmp[(tmp["attr"].str.len() > 0) & (tmp["emp"].str.len() > 0)]
        if tmp.empty:
            return
        for _, sub in tmp.groupby("attr", sort=False):
            emps = sorted(set(sub["emp"].tolist()))
            if len(emps) < 2:
                continue
            # link consecutive employees in the shared-attribute group (keeps it sparse)
            for u, v in zip(emps[:-1], emps[1:]):
                self.add_edge(u, v, edge_type)

    def incremental_refresh(self, new_events: pd.DataFrame) -> "EntityGraph":
        """Fold a NEW batch of events into the existing graph in place (hourly cadence).

        Idempotent on already-seen edges (dedup via the internal edge set), so re-feeding
        the same events does not double-count. Returns ``self`` for chaining.
        """
        return self.ingest(new_events)

    # ---------------- views ---------------- #
    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_edges(self) -> int:
        return len(self.edges)

    def node_list(self) -> list[str]:
        """All node ids with employees FIRST (in employee order), then others sorted."""
        others = sorted(n for n in self.nodes if self.nodes[n] != "employee" or n not in self.employees)
        # employees in insertion order, then any non-employee nodes
        emp_set = set(self.employees)
        rest = [n for n in others if n not in emp_set]
        return list(self.employees) + rest

    def adjacency(self, nodes: Optional[list[str]] = None) -> tuple[np.ndarray, list[str]]:
        """Dense symmetric 0/1 adjacency over ``nodes`` (default: :meth:`node_list`)."""
        nodes = nodes or self.node_list()
        idx = {n: i for i, n in enumerate(nodes)}
        n = len(nodes)
        A = np.zeros((n, n), dtype=float)
        for a, b, _t in self.edges:
            ia, ib = idx.get(a), idx.get(b)
            if ia is None or ib is None:
                continue
            A[ia, ib] = 1.0
            A[ib, ia] = 1.0
        return A, nodes

    def to_networkx(self):
        """Return a ``networkx.Graph`` with node-type / edge-type attributes, or None."""
        nx = optional_import("networkx")
        if nx is None:
            return None
        g = nx.Graph()
        for n, t in self.nodes.items():
            g.add_node(n, node_type=t)
        for a, b, t in self.edges:
            g.add_edge(a, b, edge_type=t)
        return g

    def shared_attribute_counts(self, nodes: Optional[list[str]] = None) -> pd.Series:
        """Per-node count of incident shared-attribute edges (collusion proxy)."""
        nodes = nodes or self.node_list()
        counts = {n: 0 for n in nodes}
        shared = {"shared_device", "shared_account", "shared_beneficiary"}
        for a, b, t in self.edges:
            if t in shared:
                if a in counts:
                    counts[a] += 1
                if b in counts:
                    counts[b] += 1
        return pd.Series(counts, dtype=float)


def build_entity_graph(events: pd.DataFrame) -> EntityGraph:
    """Convenience: build a fresh typed entity graph from a batch of events."""
    return EntityGraph().ingest(events)


# --------------------------------------------------------------------------- #
# k-hop aggregation                                                           #
# --------------------------------------------------------------------------- #
def _row_normalize(A: np.ndarray) -> np.ndarray:
    deg = A.sum(axis=1, keepdims=True)
    deg[deg == 0] = 1.0
    return A / deg


def _centrality(A: np.ndarray, nodes: list[str], graph: Optional[EntityGraph]) -> np.ndarray:
    """Eigenvector centrality (networkx if a graph is supplied, else power iteration)."""
    nx = optional_import("networkx")
    if graph is not None and nx is not None:
        g = graph.to_networkx()
        if g is not None and g.number_of_nodes() > 0:
            try:
                cen = nx.eigenvector_centrality_numpy(g)
            except Exception:
                cen = nx.degree_centrality(g)
            return np.array([float(cen.get(n, 0.0)) for n in nodes], dtype=float)
    # Pure-numpy power iteration on the adjacency.
    n = A.shape[0]
    if n == 0:
        return np.zeros(0)
    v = np.ones(n) / np.sqrt(n)
    for _ in range(50):
        v2 = A @ v
        nrm = np.linalg.norm(v2)
        if nrm < 1e-12:
            break
        v2 = v2 / nrm
        if np.linalg.norm(v2 - v) < 1e-8:
            v = v2
            break
        v = v2
    return np.abs(v)


def k_hop_aggregates(
    node_features: pd.DataFrame,
    adjacency: np.ndarray,
    k: int = 1,
    *,
    graph: Optional[EntityGraph] = None,
    shared_counts: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """Per-node neighbour-feature aggregates for k in {1, 2} (the GADBench lift).

    For each hop level (1..k) computes the mean/sum/max of the k-hop neighbour
    feature vectors, and always appends degree, eigenvector centrality and a
    shared-attribute count. Index/order follow ``node_features``.

    ``adjacency`` must be the dense symmetric matrix over EXACTLY the rows of
    ``node_features`` (same order). Use :meth:`EntityGraph.adjacency` to get both.
    """
    if k not in (0, 1, 2):
        raise ValueError("k must be 0, 1 or 2")
    F = node_features.to_numpy(dtype=float)
    n, d = F.shape
    nodes = [str(x) for x in node_features.index.tolist()]
    cols = [str(c) for c in node_features.columns]

    A = np.asarray(adjacency, dtype=float).copy()
    np.fill_diagonal(A, 0.0)
    deg = A.sum(axis=1)

    out = pd.DataFrame(index=node_features.index)
    out["graph_degree"] = deg
    out["graph_centrality"] = _centrality(A, nodes, graph)
    if shared_counts is not None:
        out["graph_shared_attr_count"] = shared_counts.reindex(node_features.index).fillna(0.0).to_numpy()
    elif graph is not None:
        sc = graph.shared_attribute_counts(nodes)
        out["graph_shared_attr_count"] = sc.reindex(node_features.index).fillna(0.0).to_numpy()
    else:
        out["graph_shared_attr_count"] = 0.0

    if k == 0:
        return out

    An = _row_normalize(A)        # for mean
    reach = (A > 0).astype(float)  # 1-hop reachability

    # Accumulate the per-hop aggregate columns and concat ONCE at the end. Building them
    # with repeated frame inserts fragments the DataFrame (pandas PerformanceWarning) and
    # is slow; a single concat is the pandas-3.0-recommended path. ``np.errstate`` silences
    # the spurious divide/overflow/invalid RuntimeWarnings that BLAS's blocked matmul can
    # emit for large-but-finite feature magnitudes (e.g. amount sums) — the results stay
    # finite and are guarded by the final fillna; we are not masking a real numeric error.
    blocks: list[pd.DataFrame] = [out]
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        for hop in range(1, k + 1):
            if hop == 1:
                mean_h = An @ F
                sum_h = A @ F
                # neighbour max via masked broadcasting (small graphs in L5 cadence)
                max_h = _neighbor_max(A, F)
                mask = reach
            else:
                # 2-hop reachability (exclude self and direct neighbours for the "new" ring)
                reach2 = ((reach @ reach) > 0).astype(float)
                np.fill_diagonal(reach2, 0.0)
                reach2 = reach2 * (reach == 0)  # strictly 2-hop-only
                A2n = _row_normalize(reach2)
                mean_h = A2n @ F
                sum_h = reach2 @ F
                max_h = _neighbor_max(reach2, F)
                mask = reach2

            suffix = f"_h{hop}"
            block = {}
            for j, c in enumerate(cols):
                block[f"nbr_mean_{c}{suffix}"] = mean_h[:, j]
                block[f"nbr_sum_{c}{suffix}"] = sum_h[:, j]
                block[f"nbr_max_{c}{suffix}"] = max_h[:, j]
            block[f"nbr_count{suffix}"] = mask.sum(axis=1)
            blocks.append(pd.DataFrame(block, index=node_features.index))

    return pd.concat(blocks, axis=1).fillna(0.0)


def _neighbor_max(mask: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Element-wise max of neighbour feature rows (0 where a node has no neighbours)."""
    n, d = F.shape
    out = np.zeros((n, d), dtype=float)
    for i in range(n):
        nbr = np.nonzero(mask[i] > 0)[0]
        if nbr.size:
            out[i] = F[nbr].max(axis=0)
    return out
