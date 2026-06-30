"""Proxy detection for protected attributes (ML-26; blueprint Part 29).

A model that excludes ``region`` but keeps ``branch`` can still discriminate on region if
branch is almost-determined by region — branch is a *proxy*. This module measures the
statistical dependence between each candidate (allowed) feature and each protected
attribute and flags candidates whose dependence exceeds a threshold.

Two complementary measures (both Fairlearn-independent):

* **Normalised mutual information** (categorical↔categorical, or after binning continuous
  features). MI=0 → independent; normalised so 1.0 → one determines the other. This catches
  the canonical "branch is a proxy for region/caste" case even when the relationship is
  non-monotone.
* **|correlation|** (numeric feature ↔ numeric/ordinal protected attr) as a fast linear check.

Output: a list of flagged proxies with the measure, value, and reason codes + narrative so
the finding is explainable/contestable (Part 29.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import numpy as np
import pandas as pd

from ml.base.interfaces import ReasonCode

# Above this normalised-MI (or |corr|) a candidate feature is flagged as a proxy.
DEFAULT_PROXY_THRESHOLD = 0.5


def _codes(series: pd.Series) -> np.ndarray:
    """Integer-encode a categorical/object series for MI; bin continuous numerics first."""
    s = series.reset_index(drop=True)
    if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 12:
        # bin continuous into deciles so MI is meaningful
        try:
            s = pd.qcut(s, q=10, duplicates="drop")
        except Exception:
            s = s.astype("category")
    return pd.Categorical(s.astype(str)).codes.astype(int)


def _entropy(labels: np.ndarray) -> float:
    _, counts = np.unique(labels, return_counts=True)
    p = counts / counts.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def _mutual_information(a: np.ndarray, b: np.ndarray) -> float:
    """Discrete MI between two integer-coded vectors (nats)."""
    n = len(a)
    if n == 0:
        return 0.0
    contingency = pd.crosstab(pd.Series(a), pd.Series(b)).to_numpy(dtype=float)
    pij = contingency / contingency.sum()
    pi = pij.sum(axis=1, keepdims=True)
    pj = pij.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(pij > 0, pij / (pi @ pj), 1.0)
        mi = np.where(pij > 0, pij * np.log(ratio), 0.0).sum()
    return float(max(mi, 0.0))


def normalized_mutual_information(x: pd.Series, y: pd.Series) -> float:
    """Symmetric normalised MI in [0,1] (0=independent, 1=one determines the other)."""
    ax, ay = _codes(x), _codes(y)
    n = min(len(ax), len(ay))
    ax, ay = ax[:n], ay[:n]
    mi = _mutual_information(ax, ay)
    hx, hy = _entropy(ax), _entropy(ay)
    denom = np.sqrt(hx * hy)
    if denom <= 0:
        return 0.0
    return float(np.clip(mi / denom, 0.0, 1.0))


def abs_correlation(x: pd.Series, y: pd.Series) -> Optional[float]:
    """|Pearson correlation| if both series are numeric, else None."""
    if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
        xv = pd.to_numeric(x, errors="coerce")
        yv = pd.to_numeric(y, errors="coerce")
        mask = xv.notna() & yv.notna()
        if mask.sum() < 3 or xv[mask].nunique() < 2 or yv[mask].nunique() < 2:
            return None
        return float(abs(np.corrcoef(xv[mask], yv[mask])[0, 1]))
    return None


@dataclass
class ProxyFinding:
    """One candidate-feature ↔ protected-attribute proxy relationship."""

    feature: str
    protected_attribute: str
    mutual_information: float
    correlation: Optional[float]
    measure: str
    value: float
    is_proxy: bool
    threshold: float = DEFAULT_PROXY_THRESHOLD
    reason_codes: list[dict[str, Any]] = field(default_factory=list)
    narrative: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "protected_attribute": self.protected_attribute,
            "mutual_information": round(self.mutual_information, 4),
            "correlation": None if self.correlation is None else round(self.correlation, 4),
            "measure": self.measure,
            "value": round(self.value, 4),
            "is_proxy": self.is_proxy,
            "threshold": self.threshold,
            "reason_codes": self.reason_codes,
            "narrative": self.narrative,
        }


def detect_proxies(
    features: pd.DataFrame,
    protected: pd.DataFrame,
    *,
    threshold: float = DEFAULT_PROXY_THRESHOLD,
    candidate_features: Optional[Iterable[str]] = None,
    flagged_only: bool = False,
    narrator: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> list[ProxyFinding]:
    """Score every candidate feature against every protected attribute; flag proxies.

    For each (feature, protected_attr) pair we take ``max(normalised_MI, |corr|)`` as the
    dependence measure and flag it when it exceeds ``threshold``. Flagged findings carry
    reason codes + a deterministic narrative (Part 29.2).
    """
    if narrator is None:
        from ml.narrative import render_template as _render

        def narrator(ctx: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
            return {"narrative": _render(ctx), "provider": "template"}

    feats = list(candidate_features) if candidate_features is not None else list(features.columns)
    findings: list[ProxyFinding] = []
    idx = features.index
    for attr in protected.columns:
        pa = protected[attr].reindex(idx) if not protected.index.equals(idx) else protected[attr]
        for f in feats:
            if f not in features.columns:
                continue
            col = features[f]
            nmi = normalized_mutual_information(col, pa)
            corr = abs_correlation(col, pa)
            if corr is not None and corr >= nmi:
                measure, value = "abs_correlation", corr
            else:
                measure, value = "normalized_mutual_information", nmi
            is_proxy = value >= threshold
            finding = ProxyFinding(
                feature=str(f),
                protected_attribute=str(attr),
                mutual_information=nmi,
                correlation=corr,
                measure=measure,
                value=value,
                is_proxy=is_proxy,
                threshold=threshold,
            )
            if is_proxy:
                rc = ReasonCode(
                    source="rule",
                    code=f"fairness.proxy.{f}->{attr}",
                    detail=f"Feature '{f}' is a proxy for protected attribute '{attr}' "
                    f"({measure}={value:.2f} >= {threshold:.2f}); using it can leak {attr} "
                    f"into the model.",
                    contribution=float(value),
                )
                finding.reason_codes = [rc.to_dict()]
                ctx = {
                    "alert_id": f"proxy-{f}-{attr}",
                    "entity_id": str(f),
                    "risk_score": min(100, int(round(value * 100))),
                    "severity": "high" if value >= 0.8 else "medium",
                    "reason_codes": finding.reason_codes,
                }
                narr = narrator(ctx)
                finding.narrative = narr.get("narrative")
            if is_proxy or not flagged_only:
                findings.append(finding)
    findings.sort(key=lambda fnd: fnd.value, reverse=True)
    return findings


def flagged_proxies(findings: Iterable[ProxyFinding]) -> list[ProxyFinding]:
    """Filter to only the proxy-flagged findings."""
    return [f for f in findings if f.is_proxy]
