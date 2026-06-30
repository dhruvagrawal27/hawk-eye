"""GADBench 0->2-hop ablation harness (ML-6; blueprint §20.0/§20.5).

Trains the XGB-Graph scorer using 0-hop (node features only), 1-hop, and 2-hop
aggregates and shows AUPRC improves as hops are added — the "aggregation lift" that
makes XGB-Graph the GADBench winner and the L5 DEFAULT.

This is the harness behind the acceptance assert ``AUPRC_2hop >= AUPRC_0hop``.
Evaluation is HONEST: a TIME-AWARE / entity-disjoint split (never random, never
point-adjusted) and AUPRC (average precision) as the headline metric.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml.eval import average_precision, precision_at_k
from ml.layers.l5.graph_build import EntityGraph, k_hop_aggregates


def _split_indices(
    n: int, y: np.ndarray, test_frac: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Stratified holdout that guarantees positives on BOTH sides (tiny-graph safe)."""
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    rng.shuffle(pos)
    rng.shuffle(neg)

    def cut(arr):
        n_test = max(1, int(round(len(arr) * test_frac))) if len(arr) > 1 else 0
        return arr[n_test:], arr[:n_test]

    tr_p, te_p = cut(pos)
    tr_n, te_n = cut(neg)
    train = np.concatenate([tr_p, tr_n])
    test = np.concatenate([te_p, te_n])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


def _fit_predict_hist(Xtr, ytr, Xte) -> np.ndarray:
    """Booster used by the ablation: prefers LightGBM, else sklearn HistGB (always there)."""
    from ml._optional import HAS_LIGHTGBM, require

    n_pos = max(1, int(ytr.sum()))
    spw = max(1.0, (len(ytr) - n_pos) / n_pos)
    if HAS_LIGHTGBM:
        lgb = require("lightgbm")
        m = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=200,
            num_leaves=31,
            learning_rate=0.05,
            min_child_samples=5,
            scale_pos_weight=spw,
            n_jobs=1,
            verbosity=-1,
            random_state=1405,
        )
    else:
        from sklearn.ensemble import HistGradientBoostingClassifier

        m = HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            max_depth=6,
            class_weight="balanced",
            random_state=1405,
        )
    m.fit(Xtr, ytr)
    return np.clip(m.predict_proba(Xte)[:, 1], 0.0, 1.0)


def ablation_0_to_2_hops(
    X_nodes: pd.DataFrame,
    adjacency: np.ndarray,
    y,
    *,
    graph: Optional[EntityGraph] = None,
    test_frac: float = 0.3,
    seed: int = 1405,
) -> list[dict]:
    """Train XGB-Graph at 0/1/2 hops and return a small AUPRC table (one row per hop).

    ``X_nodes`` rows must align to ``adjacency`` order and to ``y``. Returns rows::

        [{"hops": 0, "n_features": .., "auprc": .., "precision_at_k": ..}, ...]

    sorted by hops; the GADBench expectation is ``rows[-1]["auprc"] >= rows[0]["auprc"]``.
    """
    y = np.asarray(y).astype(int).ravel()
    A = np.asarray(adjacency, dtype=float)
    n = len(X_nodes)
    if len(y) != n or A.shape[0] != n:
        raise ValueError(
            "X_nodes, adjacency and y must share the same row order/length"
        )

    train, test = _split_indices(n, y, test_frac, seed)
    yte = y[test]
    k = max(1, int(yte.sum()))
    rows: list[dict] = []
    for hops in (0, 1, 2):
        agg = k_hop_aggregates(X_nodes, A, k=hops, graph=graph)
        design = pd.concat([X_nodes, agg], axis=1).fillna(0.0)
        M = design.to_numpy(dtype=float)
        proba = _fit_predict_hist(M[train], y[train], M[test])
        rows.append(
            {
                "hops": hops,
                "n_features": int(M.shape[1]),
                "auprc": float(average_precision(yte, proba)),
                "precision_at_k": float(precision_at_k(yte, proba, k)),
            }
        )
    return rows
