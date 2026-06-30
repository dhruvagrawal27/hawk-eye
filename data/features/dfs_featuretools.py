"""Automated feature generation via Deep Feature Synthesis (DATA-22; Part 6 eng. note).

featuretools' Deep Feature Synthesis (DFS) auto-generates aggregation features per
entity. featuretools is OPTIONAL here: when present we run a real DFS with the
employee as the target entity; when absent we fall back to a PURE-PANDAS groupby
aggregation that auto-generates the same family of aggregate features (count, sum,
mean, std, min, max, nunique) over every numeric/categorical column, keyed per entity.

The two paths produce a per-entity feature matrix with the SAME logical aggregations so
a model trained offline matches what online serving would compute.

Status: REAL (pure-pandas fallback). featuretools path is REAL when the lib is installed.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

E = "actor.employee_id"

try:
    import featuretools as ft  # type: ignore

    _HAVE_FT = True
except Exception:  # pragma: no cover - exercised only when ft absent
    ft = None  # type: ignore
    _HAVE_FT = False

_NUMERIC_AGGS = {
    "sum": np.sum,
    "mean": np.mean,
    "std": lambda s: np.std(s, ddof=0),
    "min": np.min,
    "max": np.max,
}


def _pure_pandas_dfs(df: pd.DataFrame, entity_col: str) -> pd.DataFrame:
    """Pure-pandas auto-aggregation fallback. Generates count + numeric aggs +
    categorical nunique per entity. Column names mirror featuretools' style
    `AGG(column)`."""
    if df.empty or entity_col not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby(entity_col)
    out = pd.DataFrame(index=sorted(map(str, df[entity_col].dropna().unique())))
    out.index.name = entity_col
    out["COUNT()"] = grouped.size().reindex(out.index).fillna(0)

    for col in df.columns:
        if col == entity_col:
            continue
        ser = df[col]
        num = pd.to_numeric(ser, errors="coerce")
        if num.notna().sum() > 0:
            tmp = df[[entity_col]].copy()
            tmp["_v"] = num
            g = tmp.groupby(entity_col)["_v"]
            for name, fn in _NUMERIC_AGGS.items():
                vals = g.apply(lambda s, fn=fn: float(fn(s.dropna())) if s.notna().any() else np.nan)
                out[f"{name.upper()}({col})"] = vals.reindex(out.index)
        else:
            nun = grouped[col].nunique()
            out[f"NUM_UNIQUE({col})"] = nun.reindex(out.index).fillna(0)
    return out


def deep_feature_synthesis(df: pd.DataFrame, entity_col: str = E,
                           index_col: Optional[str] = None) -> pd.DataFrame:
    """Auto-generate per-entity aggregation features.

    Uses featuretools DFS when available, else the pure-pandas fallback. Always returns
    a per-entity DataFrame (index = entity id).
    """
    if df.empty:
        return pd.DataFrame()
    if not _HAVE_FT:
        return _pure_pandas_dfs(df, entity_col)

    # featuretools path
    data = df.copy()
    if index_col is None:
        index_col = "_row_id"
        data[index_col] = np.arange(len(data))
    es = ft.EntitySet(id="hawkeye")
    es = es.add_dataframe(dataframe_name="events", dataframe=data,
                          index=index_col, make_index=False)
    es = es.normalize_dataframe(base_dataframe_name="events",
                                new_dataframe_name="entities",
                                index=entity_col)
    feature_matrix, _ = ft.dfs(entityset=es, target_dataframe_name="entities",
                               agg_primitives=["count", "sum", "mean", "std",
                                               "min", "max", "num_unique"],
                               trans_primitives=[], max_depth=1, verbose=False)
    feature_matrix.index = feature_matrix.index.map(str)
    return feature_matrix


def demo_frame() -> pd.DataFrame:
    """Tiny frame for the DFS demo/tests."""
    rows = []
    for i in range(6):
        rows.append({E: "EMP-a", "object.amount": 100 + i * 10, "action.verb": "post_payment"})
    for i in range(3):
        rows.append({E: "EMP-b", "object.amount": 5000 + i * 100, "action.verb": "approve_payment"})
    return pd.DataFrame(rows)
