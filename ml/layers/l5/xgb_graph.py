"""L5 DEFAULT scorer: XGB-Graph / RF-Graph (ML-6; blueprint §20.5).

Per-node features are concatenated with their k-hop aggregates (k=1..2) and fed to
a GBDT. This "aggregation + tabular booster" recipe is the GADBench winner and the
blueprint DEFAULT for L5 — it must BEAT the 0-hop baseline (see
:mod:`ml.layers.l5.gadbench_ablation`).

* :class:`XGBGraphScorer` — LightGBM (default) / XGBoost / sklearn HistGB fallback.
* :class:`RFGraphScorer`  — RandomForest variant.

Both subclass :class:`ml.base.BaseScorer`: ``predict_proba`` returns P(fraud) in
[0,1]; ``reason_codes`` surfaces the top contributing features (including which
graph aggregate fired) as ``ReasonCode(source="graph"|"shap")``.

The module ALWAYS imports — boosters are imported inside ``fit``/methods and degrade
to scikit-learn when LightGBM/XGBoost are absent.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_LIGHTGBM, HAS_XGBOOST, optional_import
from ml.base import BaseScorer, ReasonCode
from ml.layers.l5.graph_build import EntityGraph, build_entity_graph, k_hop_aggregates


def _align_node_features(
    entity_features: pd.DataFrame, graph: EntityGraph
) -> tuple[pd.DataFrame, np.ndarray]:
    """Build the node-feature matrix over the FULL graph node set + its adjacency.

    Employee rows carry their real ``entity_features``; non-employee nodes
    (accounts/beneficiaries/devices/vendors) get zero feature rows so the k-hop
    aggregation can still flow signal through them. Returns (node_features, adjacency)
    in the SAME node order.
    """
    A, nodes = graph.adjacency()
    cols = list(entity_features.columns)
    F = pd.DataFrame(0.0, index=pd.Index(nodes, name="node"), columns=cols)
    common = [n for n in nodes if n in entity_features.index]
    if common:
        F.loc[common, cols] = entity_features.loc[common, cols].to_numpy(dtype=float)
    return F, A


def graph_design_matrix(
    entity_features: pd.DataFrame, graph: EntityGraph, k: int = 2
) -> pd.DataFrame:
    """Node features ⊕ k-hop aggregates, restricted to the EMPLOYEE rows (primary entity)."""
    node_feat, A = _align_node_features(entity_features, graph)
    agg = k_hop_aggregates(node_feat, A, k=k, graph=graph)
    full = pd.concat([node_feat, agg], axis=1)
    # Keep only the primary entities (employees) that we have labels/features for.
    emp_index = [e for e in entity_features.index if e in full.index]
    X = full.loc[emp_index]
    X.index = pd.Index(emp_index, name=entity_features.index.name or "employee_id")
    return X.fillna(0.0)


class _BaseGraphScorer(BaseScorer):
    """Shared plumbing: build graph -> design matrix -> GBDT; graph reason codes."""

    layer = "L5"

    def __init__(self, name: str, *, k: int = 2, version: str = "0.1.0") -> None:
        super().__init__(name=name, version=version)
        self.k = int(k)
        self._model = None
        self._impl = "none"
        self._columns: list[str] = []
        self._graph: Optional[EntityGraph] = None
        self._feature_index: Optional[pd.Index] = None

    # subclasses build the estimator
    def _make_model(self, n_pos: int, n_neg: int):  # pragma: no cover - overridden
        raise NotImplementedError

    def _build_design(self, X: pd.DataFrame, events: Optional[pd.DataFrame]) -> pd.DataFrame:
        """X is per-employee entity_features. ``events`` (optional) builds/refreshes the graph."""
        if events is not None:
            self._graph = build_entity_graph(events)
        if self._graph is None:
            # Degenerate fallback: identity graph (k-hop aggregates become zeros/degree 0)
            self._graph = EntityGraph()
            for e in [str(i) for i in X.index]:
                self._graph.add_node(e, "employee")
                if e not in self._graph.employees:
                    self._graph.employees.append(e)
        return graph_design_matrix(X, self._graph, k=self.k)

    def fit(self, X: pd.DataFrame, y, events: Optional[pd.DataFrame] = None) -> "_BaseGraphScorer":
        design = self._build_design(X, events)
        y = pd.Series(np.asarray(y).astype(int).ravel(), index=X.index).reindex(design.index).fillna(0).astype(int)
        self._columns = [str(c) for c in design.columns]
        Xv = design.to_numpy(dtype=float)
        yv = y.to_numpy(dtype=int)
        n_pos = int(yv.sum())
        n_neg = int(len(yv) - n_pos)
        self._model = self._make_model(n_pos, n_neg)
        self._model.fit(Xv, yv)
        self._feature_index = design.index
        self._fitted = True
        return self

    def _design_for(self, X: pd.DataFrame, events: Optional[pd.DataFrame]) -> pd.DataFrame:
        graph = build_entity_graph(events) if events is not None else self._graph
        if graph is None:
            graph = EntityGraph()
            for e in [str(i) for i in X.index]:
                graph.add_node(e, "employee")
                if e not in graph.employees:
                    graph.employees.append(e)
        design = graph_design_matrix(X, graph, k=self.k)
        # align to training columns
        for c in self._columns:
            if c not in design.columns:
                design[c] = 0.0
        return design[self._columns]

    def predict_proba(self, X: pd.DataFrame, events: Optional[pd.DataFrame] = None) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise RuntimeError("scorer is not fitted")
        design = self._design_for(X, events)
        Xv = design.to_numpy(dtype=float)
        proba = self._model.predict_proba(Xv)[:, 1]
        return np.clip(np.asarray(proba, dtype=float).ravel(), 0.0, 1.0)

    def _importances(self) -> np.ndarray:
        m = self._model
        imp = getattr(m, "feature_importances_", None)
        if imp is None:
            return np.ones(len(self._columns))
        return np.asarray(imp, dtype=float)

    def reason_codes(
        self, X: pd.DataFrame, top_k: int = 5, events: Optional[pd.DataFrame] = None
    ) -> list[list[ReasonCode]]:
        """Top contributing features per employee. Graph aggregates -> source='graph'."""
        if not self._fitted:
            return [[] for _ in range(len(X))]
        design = self._design_for(X, events)
        gimp = self._importances()
        gimp = gimp / (gimp.sum() or 1.0)
        cols = self._columns
        Xv = design.to_numpy(dtype=float)
        # Per-row contribution proxy = global importance * standardized feature value.
        col_mean = Xv.mean(axis=0)
        col_std = Xv.std(axis=0)
        col_std[col_std == 0] = 1.0
        z = (Xv - col_mean) / col_std
        out: list[list[ReasonCode]] = []
        for i in range(Xv.shape[0]):
            contrib = gimp * np.abs(z[i])
            order = np.argsort(-contrib)[:top_k]
            rcs: list[ReasonCode] = []
            for j in order:
                name = cols[j]
                is_graph = name.startswith(("nbr_", "graph_"))
                rcs.append(
                    ReasonCode(
                        source="graph" if is_graph else "shap",
                        feature=name,
                        detail=f"{'k-hop graph aggregate' if is_graph else 'node feature'} {name}={Xv[i, j]:.3g}",
                        contribution=float(contrib[j]),
                    )
                )
            out.append(rcs)
        return out


class XGBGraphScorer(_BaseGraphScorer):
    """DEFAULT L5 scorer: k-hop aggregates -> gradient-boosted trees.

    Booster preference: LightGBM -> XGBoost -> sklearn HistGradientBoosting (always
    available). Uses the L3 imbalance recipe (``scale_pos_weight``/``is_unbalance``).
    """

    def __init__(self, *, k: int = 2, backend: str = "auto", version: str = "0.1.0") -> None:
        super().__init__(name="l5-xgb-graph", k=k, version=version)
        self.backend = backend

    def _make_model(self, n_pos: int, n_neg: int):
        spw = max(1.0, n_neg / max(1, n_pos))
        want = self.backend
        if want in ("auto", "lightgbm") and HAS_LIGHTGBM:
            lgb = optional_import("lightgbm")
            self._impl = "lightgbm"
            return lgb.LGBMClassifier(
                objective="binary",
                n_estimators=300,
                num_leaves=31,
                learning_rate=0.05,
                feature_fraction=0.8,
                bagging_fraction=0.8,
                bagging_freq=1,
                min_child_samples=10,
                scale_pos_weight=spw,
                n_jobs=1,
                verbosity=-1,
                random_state=1405,
            )
        if want in ("auto", "xgboost") and HAS_XGBOOST:
            xgb = optional_import("xgboost")
            self._impl = "xgboost"
            return xgb.XGBClassifier(
                tree_method="hist",
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=5,
                eval_metric="aucpr",
                scale_pos_weight=spw,
                n_jobs=1,
                random_state=1405,
            )
        from sklearn.ensemble import HistGradientBoostingClassifier

        self._impl = "sklearn-histgb"
        return HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            max_depth=6,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=1405,
        )


class RFGraphScorer(_BaseGraphScorer):
    """RandomForest variant of the graph scorer (robust, no booster dependency)."""

    def __init__(self, *, k: int = 2, n_estimators: int = 300, version: str = "0.1.0") -> None:
        super().__init__(name="l5-rf-graph", k=k, version=version)
        self.n_estimators = int(n_estimators)

    def _make_model(self, n_pos: int, n_neg: int):
        from sklearn.ensemble import RandomForestClassifier

        self._impl = "sklearn-rf"
        return RandomForestClassifier(
            n_estimators=self.n_estimators,
            max_depth=None,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            n_jobs=1,
            random_state=1405,
        )
