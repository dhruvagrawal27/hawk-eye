"""Benchmark the three L3 GBDT scorers on a TIME-BASED split (ML-4; blueprint Part 20.3, 22.2).

Trains LightGBM / XGBoost / CatBoost on a temporal split (past->future, NEVER random),
evaluates each with the honest ``ml.eval`` harness (average_precision is primary) plus
median predict latency, returns a ranked table, and picks the best (tie-break -> LightGBM,
the blueprint default). All three are then available to L6 fusion.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ml import eval as mleval
from ml.base import BaseScorer
from ml.layers.l3.calibration import CalibratedScorer
from ml.layers.l3.catboost_scorer import CatBoostScorer
from ml.layers.l3.imbalance import _as_label_array
from ml.layers.l3.lightgbm_scorer import LightGBMScorer
from ml.layers.l3.xgboost_scorer import XGBoostScorer

# Blueprint tie-break order: LightGBM is the default GBDT.
_PRIORITY = {"l3_lightgbm": 0, "l3_xgboost": 1, "l3_catboost": 2}


@dataclass
class BenchmarkResult:
    table: list[dict]
    best_name: str
    best_scorer: BaseScorer
    fitted: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"table": self.table, "best_name": self.best_name}


def _temporal_split_xy(
    X: pd.DataFrame, y, ts: Optional[pd.Series], test_frac: float
) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame, np.ndarray]:
    """Split (X, y) by time. Uses ``ts`` via ml.eval.temporal_split if given, else index order."""
    yarr = _as_label_array(y)
    Xr = X.reset_index(drop=True)
    if ts is not None:
        df = Xr.copy()
        df["__ts__"] = np.asarray(ts)
        df["__y__"] = yarr
        tr, te = mleval.temporal_split(df, "__ts__", test_frac=test_frac)
        y_tr = tr["__y__"].to_numpy()
        y_te = te["__y__"].to_numpy()
        X_tr = tr.drop(columns=["__ts__", "__y__"])
        X_te = te.drop(columns=["__ts__", "__y__"])
        return X_tr.reset_index(drop=True), y_tr, X_te.reset_index(drop=True), y_te
    # Index-order split (rows assumed already time-ordered).
    n = len(Xr)
    cut = max(1, min(int(round(n * (1 - test_frac))), n - 1))
    return (
        Xr.iloc[:cut].reset_index(drop=True),
        yarr[:cut],
        Xr.iloc[cut:].reset_index(drop=True),
        yarr[cut:],
    )


def _default_scorers() -> dict[str, BaseScorer]:
    return {
        "l3_lightgbm": LightGBMScorer(),
        "l3_xgboost": XGBoostScorer(),
        "l3_catboost": CatBoostScorer(),
    }


def benchmark_scorers(
    X: pd.DataFrame,
    y,
    *,
    ts: Optional[pd.Series] = None,
    test_frac: float = 0.25,
    calibrate: bool = True,
    scorers: Optional[dict[str, BaseScorer]] = None,
    k: Optional[int] = None,
) -> BenchmarkResult:
    """Train all three L3 scorers on a time-based split and rank by held-out average precision.

    Returns a ``BenchmarkResult`` with the ranked table (each row has average_precision,
    precision_at_k, recall_at_k, predict latency) and the chosen best scorer (tie-break ->
    LightGBM). When ``calibrate`` is True each scorer is wrapped in ``CalibratedScorer`` so
    its probabilities are real probabilities.
    """
    X = X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X))
    X_tr, y_tr, X_te, y_te = _temporal_split_xy(X, y, ts, test_frac)

    scorers = scorers or _default_scorers()
    rows: list[dict] = []
    fitted: dict[str, BaseScorer] = {}

    for name, base in scorers.items():
        model: BaseScorer = CalibratedScorer(base, method="isotonic") if calibrate else base
        model.fit(X_tr, y_tr)
        # measure single-batch predict latency (whole test block).
        t0 = time.perf_counter()
        p = model.predict_proba(X_te)
        latency_ms = (time.perf_counter() - t0) * 1000.0 / max(1, len(X_te))

        rep = mleval.evaluate(y_te, p, name=name, k=k).to_dict()
        rep["predict_latency_ms_per_row"] = round(float(latency_ms), 4)
        rep["backend"] = getattr(base, "_backend", "unknown")
        rows.append(rep)
        fitted[name] = model

    # Rank by average_precision desc; tie-break by blueprint priority (LightGBM first).
    rows_sorted = sorted(
        rows,
        key=lambda r: (-r["average_precision"], _PRIORITY.get(r["name"], 99)),
    )
    best_name = rows_sorted[0]["name"]
    return BenchmarkResult(
        table=rows_sorted,
        best_name=best_name,
        best_scorer=fitted[best_name],
        fitted=fitted,
    )
