"""TreeSHAP reason codes for L3 GBDT scorers (ML-4; blueprint Part 20.6, 18).

LIVE path = PLAIN TreeSHAP only (exact/fast, ~5-20ms; blueprint Part 18). Interaction
values are EXPENSIVE and OFFLINE-ONLY (``offline_interaction_values`` below, clearly
marked). Each per-row explanation is a ``list[ReasonCode(source="shap", feature=,
contribution=)]`` ranked by |contribution|.

The heavy ``shap`` import stays INSIDE the functions so the module always imports. When
shap is absent we fall back to a crude ``feature_importances_ * feature_value`` contribution
so reason codes are still produced (degraded, but the contract holds).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml._optional import optional_import
from ml.base import ReasonCode


def _feature_names(X) -> list[str]:
    cols = getattr(X, "columns", None)
    if cols is not None:
        return [str(c) for c in cols]
    arr = np.asarray(X)
    width = arr.shape[1] if arr.ndim == 2 else 0
    return [f"f{i}" for i in range(width)]


def _positive_class_shap(values: Any) -> np.ndarray:
    """Normalise shap output to a (n_rows, n_features) array for the positive class."""
    arr = np.asarray(values)
    if arr.ndim == 3:
        # (n_rows, n_features, n_classes) or (n_classes, n_rows, n_features)
        if arr.shape[-1] == 2:
            return arr[:, :, 1]
        if arr.shape[0] == 2:
            return arr[1]
        return arr[..., -1]
    return arr


def tree_shap_reason_codes(model: Any, X, top_k: int = 5) -> list[list[ReasonCode]]:
    """Plain TreeSHAP per-row reason codes (NO interaction values — hot-path safe).

    Returns one ``list[ReasonCode]`` per row, the ``top_k`` features by |SHAP value|,
    ordered most-influential first, ``source="shap"``.
    """
    names = _feature_names(X)
    Xdf = (
        X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X), columns=names)
    )
    shap = optional_import("shap")

    if shap is not None:
        try:
            explainer = shap.TreeExplainer(model)
            # check_additivity off keeps it fast/robust across tree backends.
            sv = explainer.shap_values(Xdf, check_additivity=False)
            mat = _positive_class_shap(sv)
            return _rank_from_matrix(mat, names, top_k)
        except Exception:
            pass  # fall through to crude importance fallback

    return _fallback_importance_codes(model, Xdf, names, top_k)


def _rank_from_matrix(
    mat: np.ndarray, names: list[str], top_k: int
) -> list[list[ReasonCode]]:
    mat = np.atleast_2d(np.asarray(mat, dtype=float))
    n_rows, n_feat = mat.shape
    k = max(1, min(int(top_k), n_feat))
    out: list[list[ReasonCode]] = []
    for i in range(n_rows):
        row = mat[i]
        order = np.argsort(-np.abs(row))[:k]
        codes = [
            ReasonCode(
                source="shap",
                feature=names[j] if j < len(names) else f"f{j}",
                contribution=float(row[j]),
            )
            for j in order
        ]
        out.append(codes)
    return out


def _fallback_importance_codes(
    model: Any, Xdf: pd.DataFrame, names: list[str], top_k: int
) -> list[list[ReasonCode]]:
    """Crude contribution = feature_importance * standardized feature value (no shap)."""
    imp = getattr(model, "feature_importances_", None)
    if imp is None:
        imp = np.ones(Xdf.shape[1], dtype=float)
    imp = np.asarray(imp, dtype=float)
    if imp.sum() > 0:
        imp = imp / imp.sum()
    vals = Xdf.to_numpy(dtype=float)
    mu = vals.mean(axis=0)
    sd = vals.std(axis=0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    z = (vals - mu) / sd
    contrib = z * imp  # (n_rows, n_feat)
    return _rank_from_matrix(contrib, names, top_k)


# --------------------------------------------------------------------------- #
# OFFLINE ONLY — do NOT call on the serving hot path (blueprint Part 20.6/18). #
# --------------------------------------------------------------------------- #
def offline_interaction_values(model: Any, X) -> np.ndarray:
    """SHAP interaction values — OFFLINE ANALYSIS ONLY (expensive, never online).

    Returns the (n_rows, n_features, n_features) interaction tensor for the positive
    class. This is O(n_features^2) per row and must run in batch/analysis jobs, never on
    the ~100-300ms scoring path (blueprint Part 18). Raises if shap is unavailable.
    """
    shap = optional_import("shap")
    if shap is None:
        raise ImportError(
            "offline_interaction_values requires 'shap'. This is an OFFLINE helper; "
            "never wire it into online scoring."
        )
    names = _feature_names(X)
    Xdf = (
        X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X), columns=names)
    )
    explainer = shap.TreeExplainer(model)
    inter = explainer.shap_interaction_values(Xdf)
    arr = np.asarray(inter)
    if arr.ndim == 4:  # (n_classes, n_rows, n_feat, n_feat)
        arr = arr[-1]
    return arr
