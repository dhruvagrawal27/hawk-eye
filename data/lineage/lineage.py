"""End-to-end data lineage: source -> feature -> model -> alert (DATA-25).

Blueprint Part 21.5 (storage & versioning, l.822-826), Part 28.2 (data lineage, l.1205):
"end-to-end (source -> feature -> model -> alert), for audit, debugging, and DPDP
traceability"; every model records the DATASET HASH + FEATURE-SET VERSION it trained on.
Status: REAL (DVC/MLflow are OPTIONAL; the content hash is pure-python/pandas).

Provides:
  - ``content_hash(df_or_bytes)`` : a stable SHA-256 content hash of a dataset (used as
    the DVC/MLflow data-artifact content address). Stable across row order? No — order
    matters for events; we hash the canonical bytes so the SAME dataframe yields the SAME
    hash, and a single changed cell changes it.
  - ``feature_set_version(feature_names)`` : a deterministic version string for a set of
    feature definitions (so a model records which feature surface it used).
  - ``LineageGraph`` : an append-only DAG of nodes (datasets/features/models/alerts) and
    edges, with a ``record_training_lineage`` helper that wires source->feature->model and
    ``link_alert`` that wires model->alert.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Union

import pandas as pd

# ---- optional DVC / MLflow (content hash works without them) ----------------
try:  # pragma: no cover
    import mlflow  # type: ignore  # noqa: F401

    _HAVE_MLFLOW = True
except Exception:  # pragma: no cover
    _HAVE_MLFLOW = False


def content_hash(data: Union[pd.DataFrame, bytes, str]) -> str:
    """Stable SHA-256 content hash of a dataset.

    For a DataFrame we serialize to a canonical CSV byte stream (column order preserved,
    index dropped) so the SAME data yields the SAME hash deterministically, and any cell
    change flips it. This is the dataset content address recorded per model.
    """
    if isinstance(data, pd.DataFrame):
        buf = io.StringIO()
        # Sort columns for a canonical layout; keep row order (event order matters).
        data = data[sorted(data.columns)]
        data.to_csv(buf, index=False)
        raw = buf.getvalue().encode("utf-8")
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = data
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def feature_set_version(feature_names: Iterable[str]) -> str:
    """Deterministic version id for a feature set (order-independent).

    Two models built on the same feature definitions get the same version; adding/removing
    a feature changes it. Recorded alongside the dataset hash per model.
    """
    canon = "|".join(sorted(set(feature_names)))
    return "fsv_" + hashlib.sha256(canon.encode("utf-8")).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class LineageNode:
    node_id: str
    kind: str             # source | feature | model | alert | dataset
    attrs: tuple[tuple[str, Any], ...] = ()  # frozen attrs for hashability

    @property
    def attr_dict(self) -> dict[str, Any]:
        return dict(self.attrs)


@dataclass(frozen=True)
class LineageEdge:
    src: str
    dst: str
    relation: str         # produces | derives | trains | scores
    ts: str = field(default_factory=_now_iso)


@dataclass
class LineageGraph:
    """Append-only lineage DAG."""

    nodes: dict[str, LineageNode] = field(default_factory=dict)
    edges: list[LineageEdge] = field(default_factory=list)

    def add_node(self, node_id: str, kind: str, **attrs: Any) -> LineageNode:
        node = LineageNode(node_id, kind, tuple(sorted(attrs.items())))
        self.nodes[node_id] = node
        return node

    def add_edge(self, src: str, dst: str, relation: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError("both endpoints must be added before linking")
        self.edges.append(LineageEdge(src, dst, relation))

    def ancestors(self, node_id: str) -> set[str]:
        """All upstream nodes feeding ``node_id`` (for audit/DPDP traceability)."""
        incoming: dict[str, list[str]] = {}
        for e in self.edges:
            incoming.setdefault(e.dst, []).append(e.src)
        seen: set[str] = set()
        stack = list(incoming.get(node_id, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(incoming.get(n, []))
        return seen

    def to_records(self) -> list[dict[str, Any]]:
        return [{"src": e.src, "dst": e.dst, "relation": e.relation, "ts": e.ts}
                for e in self.edges]


def record_training_lineage(
    graph: LineageGraph,
    *,
    source_id: str,
    dataset: pd.DataFrame,
    feature_names: list[str],
    model_id: str,
) -> dict[str, str]:
    """Record source -> dataset -> feature-set -> model lineage.

    Returns the {dataset_hash, feature_set_version} a model registry should pin. The
    SAME dataset + feature set always yields the SAME pair (stability), satisfying the
    DATA-25 acceptance check.
    """
    ds_hash = content_hash(dataset)
    fsv = feature_set_version(feature_names)

    graph.add_node(source_id, "source")
    dataset_id = f"dataset:{ds_hash}"
    graph.add_node(dataset_id, "dataset", content_hash=ds_hash, rows=len(dataset))
    fs_id = f"featureset:{fsv}"
    graph.add_node(fs_id, "feature", version=fsv, features=tuple(sorted(feature_names)))
    graph.add_node(model_id, "model", dataset_hash=ds_hash, feature_set_version=fsv)

    graph.add_edge(source_id, dataset_id, "produces")
    graph.add_edge(dataset_id, fs_id, "derives")
    graph.add_edge(fs_id, model_id, "trains")
    return {"dataset_hash": ds_hash, "feature_set_version": fsv}


def link_alert(graph: LineageGraph, model_id: str, alert_id: str) -> None:
    """Wire model -> alert, completing source->feature->model->alert lineage."""
    if alert_id not in graph.nodes:
        graph.add_node(alert_id, "alert")
    graph.add_edge(model_id, alert_id, "scores")
