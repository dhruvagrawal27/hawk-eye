"""Fairness mitigations (ML-26; blueprint Part 29).

Three mitigation surfaces, in order of preference per the blueprint:

1. **Peer-group-relative scoring** (``peer_relative_mitigation``) — reuse
   ``ml.design.peer_relative_scores``. Normalising each entity against its peer group
   removes role/branch/department base-rate differences and is the primary, least-invasive
   fairness lever. This is preferred over flipping decisions.
2. **Pre/in/post-processing** where gaps remain:
   * post-processing group-wise thresholds (``group_wise_thresholds`` /
     ``apply_group_thresholds``) — equalise selection or TPR per group;
   * Fairlearn ``ThresholdOptimizer`` (``threshold_optimizer``) when available.
3. **Protected-attribute exclusion** (``assert_no_protected_features``) — the hard rule:
   protected attributes (and known proxies) must NEVER be model features.

ALERT-ONLY: mitigations adjust *score normalisation / alerting thresholds*; they never
auto-block a person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from ml._optional import optional_import
from ml.design import peer_relative_scores, peer_relative_unit
from ml.fairness.metrics import PROTECTED_ATTRIBUTES

# Column-name fragments that indicate a protected attribute leaked in as a feature.
_PROTECTED_NAME_FRAGMENTS = (
    "grade",
    "seniority",
    "gender",
    "sex",
    "age",
    "region",
    "branch",
    "caste",
    "religion",
    "department",
    "dept",
    "ethnicity",
    "race",
    "marital",
    "disab",
)


class ProtectedFeatureLeak(AssertionError):
    """Raised when a protected attribute (or known proxy) is used as a model feature."""


def find_protected_features(
    feature_names: Iterable[str], *, extra_protected: Optional[Iterable[str]] = None
) -> list[str]:
    """Return feature names that look like protected attributes (name-fragment match)."""
    fragments = set(_PROTECTED_NAME_FRAGMENTS)
    for attr in list(PROTECTED_ATTRIBUTES) + list(extra_protected or []):
        fragments.add(attr.lower())
    hits: list[str] = []
    for name in feature_names:
        low = str(name).lower()
        # tenure is a special case: a derived tenure FEATURE is allowed (it's behavioural),
        # but a raw protected "tenure" *attribute* used as the grouping key is not. We flag
        # only explicit protected fragments, leaving derived behavioural columns alone.
        if any(frag in low for frag in fragments):
            hits.append(str(name))
    return hits


def assert_no_protected_features(
    feature_names: Iterable[str],
    *,
    extra_protected: Optional[Iterable[str]] = None,
    allow: Optional[Iterable[str]] = None,
) -> None:
    """Assert protected attributes are EXCLUDED from features. Raise ProtectedFeatureLeak if not.

    ``allow`` is an explicit allow-list of column names that, despite matching a protected
    fragment, are legitimately behavioural and pre-vetted (e.g. a derived ``tenure_days``
    behavioural feature). Everything else that matches is treated as a leak.
    """
    allow_set = {str(a) for a in (allow or [])}
    hits = [
        h
        for h in find_protected_features(feature_names, extra_protected=extra_protected)
        if h not in allow_set
    ]
    if hits:
        raise ProtectedFeatureLeak(
            "protected attributes must not be used as model features; found: "
            + ", ".join(sorted(hits))
        )


# --------------------------------------------------------------------------- #
# 1. Peer-group-relative scoring (preferred mitigation)                        #
# --------------------------------------------------------------------------- #
def peer_relative_mitigation(
    scores: pd.Series, peer_groups: pd.Series, *, unit: bool = True, **kw: Any
) -> pd.Series:
    """Peer-group-relative re-scoring (reuses ``ml.design.peer_relative_scores``).

    ``unit=True`` squashes to [0,1] (fusion-ready). This is the primary fairness lever:
    "anomalous for your peers", not "high in absolute terms".
    """
    if unit:
        return peer_relative_unit(scores, peer_groups, **kw)
    return peer_relative_scores(scores, peer_groups, **kw)


# --------------------------------------------------------------------------- #
# 2a. Post-processing: group-wise thresholds (direct)                          #
# --------------------------------------------------------------------------- #
@dataclass
class GroupThresholds:
    """Per-group decision thresholds (post-processing mitigation)."""

    thresholds: dict[str, float] = field(default_factory=dict)
    global_threshold: float = 0.5
    objective: str = "selection_rate"

    def threshold_for(self, group: str) -> float:
        return self.thresholds.get(str(group), self.global_threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "thresholds": {k: round(v, 4) for k, v in self.thresholds.items()},
            "global_threshold": round(self.global_threshold, 4),
            "objective": self.objective,
        }


def group_wise_thresholds(
    y_score: Iterable[float],
    sensitive: Iterable[Any],
    *,
    target_rate: Optional[float] = None,
    y_true: Optional[Iterable[Any]] = None,
    objective: str = "selection_rate",
) -> GroupThresholds:
    """Compute per-group thresholds so each group hits a common ``target_rate``.

    ``objective="selection_rate"``: equalise the fraction flagged per group (demographic
    parity). ``objective="tpr"`` (needs ``y_true``): equalise recall on true fraud
    (equal-opportunity). If ``target_rate`` is None it defaults to the overall pooled rate.
    """
    s = pd.Series(np.asarray(list(y_score), dtype=float))
    grp = pd.Series([str(g) for g in sensitive], index=s.index)

    if objective == "tpr":
        if y_true is None:
            raise ValueError("objective='tpr' requires y_true")
        yt = pd.Series(np.asarray(list(y_true), dtype=float).astype(int), index=s.index)
        pooled = (
            target_rate
            if target_rate is not None
            else float((yt == 1).mean() and (s[yt == 1] >= s.median()).mean())
        )
        thresholds: dict[str, float] = {}
        for g in pd.unique(grp):
            mask = (grp.values == g) & (yt.values == 1)
            pos = s[mask]
            if len(pos) == 0:
                thresholds[str(g)] = float(s.median())
                continue
            # threshold = quantile so a (1 - target_rate) fraction of positives are flagged.
            q = float(np.clip(1.0 - (pooled or 0.5), 0.0, 1.0))
            thresholds[str(g)] = float(np.quantile(pos, q))
        return GroupThresholds(
            thresholds=thresholds,
            global_threshold=float(s.median()),
            objective=objective,
        )

    # selection_rate objective
    pooled = target_rate if target_rate is not None else float((s >= s.median()).mean())
    thresholds = {}
    for g in pd.unique(grp):
        vals = s[grp.values == g]
        if len(vals) == 0:
            thresholds[str(g)] = float(s.median())
            continue
        q = float(np.clip(1.0 - pooled, 0.0, 1.0))
        thresholds[str(g)] = float(np.quantile(vals, q))
    return GroupThresholds(
        thresholds=thresholds,
        global_threshold=float(np.quantile(s, 1.0 - pooled)),
        objective=objective,
    )


def apply_group_thresholds(
    y_score: Iterable[float], sensitive: Iterable[Any], gt: GroupThresholds
) -> np.ndarray:
    """Apply per-group thresholds -> 0/1 decisions (post-processing mitigation)."""
    s = np.asarray(list(y_score), dtype=float)
    groups = [str(g) for g in sensitive]
    return np.array(
        [1 if s[i] >= gt.threshold_for(groups[i]) else 0 for i in range(len(s))],
        dtype=int,
    )


# --------------------------------------------------------------------------- #
# 2b. Post-processing: Fairlearn ThresholdOptimizer (when available)           #
# --------------------------------------------------------------------------- #
def _make_constant_estimator(scores: np.ndarray) -> Any:
    """Adapter so a precomputed score vector can drive Fairlearn's ThresholdOptimizer.

    Built lazily so importing this module never hard-depends on sklearn's BaseEstimator
    being present; falls back to a plain object if sklearn is unavailable.
    """
    sk = optional_import("sklearn")
    base = sk.base.BaseEstimator if sk is not None else object

    class _ConstantEstimator(base):  # type: ignore[misc, valid-type]
        def __init__(self, scores: np.ndarray) -> None:
            self._scores = np.asarray(scores, dtype=float)
            self.is_fitted_ = True  # sklearn check_is_fitted convention

        def fit(self, X: Any, y: Any = None, **kw: Any) -> "_ConstantEstimator":
            self.is_fitted_ = True
            return self

        def predict(self, X: Any) -> np.ndarray:
            idx = np.asarray(X).ravel().astype(int)
            return self._scores[idx]

        # ThresholdOptimizer with predict_method='predict' uses predict(); provide both.
        def predict_proba(self, X: Any) -> np.ndarray:
            p = self.predict(X)
            return np.column_stack([1 - p, p])

    return _ConstantEstimator(scores)


@dataclass
class ThresholdOptimizerResult:
    available: bool
    y_pred: Optional[np.ndarray] = None
    backend: str = "fairlearn"
    constraint: str = "demographic_parity"


def threshold_optimizer(
    y_score: Iterable[float],
    y_true: Iterable[Any],
    sensitive: Iterable[Any],
    *,
    constraint: str = "demographic_parity",
) -> ThresholdOptimizerResult:
    """Fairlearn ThresholdOptimizer post-processing (group-wise thresholds learned jointly).

    Falls back to ``available=False`` if Fairlearn is absent, so callers can degrade to the
    direct ``group_wise_thresholds`` mitigation. ``constraint`` in
    {'demographic_parity','equalized_odds','true_positive_rate_parity', ...} per Fairlearn.
    """
    fl = optional_import("fairlearn")
    if fl is None:
        return ThresholdOptimizerResult(
            available=False, backend="direct", constraint=constraint
        )
    try:
        from fairlearn.postprocessing import ThresholdOptimizer

        scores = np.asarray(list(y_score), dtype=float)
        yt = np.asarray(list(y_true), dtype=float).astype(int)
        sf = np.array([str(g) for g in sensitive])
        idx = np.arange(len(scores)).reshape(-1, 1)

        opt = ThresholdOptimizer(
            estimator=_make_constant_estimator(scores),
            constraints=constraint,
            objective="balanced_accuracy_score",
            predict_method="predict",
            prefit=True,
        )
        opt.fit(idx, yt, sensitive_features=sf)
        rng = np.random.RandomState(0)
        y_pred = np.asarray(
            opt.predict(idx, sensitive_features=sf, random_state=rng)
        ).astype(int)
        return ThresholdOptimizerResult(
            available=True, y_pred=y_pred, constraint=constraint
        )
    except Exception:
        return ThresholdOptimizerResult(
            available=False, backend="direct", constraint=constraint
        )
