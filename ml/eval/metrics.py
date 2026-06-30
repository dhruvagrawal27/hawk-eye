"""Honest, leakage-safe detection metrics (ML-2; blueprint Part 14, 20.0/20.4).

THE NON-NEGOTIABLE RULE: **point-adjust (PA) is never implemented here.** PA can make
random scores look SOTA (Kim'22, Wu&Keogh), so there is deliberately no PA function to
select. Time-series quality is measured with **range/affiliation-aware PR** and **VUS-PR**.
Every comparison helper forces a random baseline into the table.

Metrics provided (Part 14):
- ``average_precision`` / ``pr_auc`` (NOT ROC-AUC alone — flatters imbalance)
- ``precision_at_k``, ``recall_at_k``, ``alert_to_true_ratio``
- ``recall_on_known_cases``, ``time_to_detection``
- ``range_based_precision/recall`` (Tatbul et al.), ``vus_pr`` (Paparrizos et al.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np
from sklearn.metrics import average_precision_score

# Explicit, load-bearing constant: point-adjust is disabled by construction.
POINT_ADJUST_ENABLED = False


def _arrays(y_true: Sequence, scores: Sequence) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y_true).astype(int).ravel()
    s = np.asarray(scores, dtype=float).ravel()
    if y.shape != s.shape:
        raise ValueError(f"y_true {y.shape} and scores {s.shape} must match")
    return y, s


def average_precision(y_true: Sequence, scores: Sequence) -> float:
    """Average precision = area under the PR curve (the primary metric for imbalance)."""
    y, s = _arrays(y_true, scores)
    if y.sum() == 0 or y.sum() == y.size:
        return float(y.mean())
    return float(average_precision_score(y, s))


pr_auc = average_precision  # alias


def precision_at_k(y_true: Sequence, scores: Sequence, k: int) -> float:
    """Precision among the top-k highest-scored items."""
    y, s = _arrays(y_true, scores)
    k = max(1, min(int(k), y.size))
    top = np.argsort(-s)[:k]
    return float(y[top].sum() / k)


def recall_at_k(y_true: Sequence, scores: Sequence, k: int) -> float:
    """Recall (of all positives) captured in the top-k."""
    y, s = _arrays(y_true, scores)
    total = int(y.sum())
    if total == 0:
        return 0.0
    k = max(1, min(int(k), y.size))
    top = np.argsort(-s)[:k]
    return float(y[top].sum() / total)


def alert_to_true_ratio(y_true: Sequence, scores: Sequence, k: int) -> float:
    """Alerts raised per true fraud caught in the top-k (analyst-burden metric).

    = k / (#true positives in top-k). Lower is better; inf if no true positive caught.
    """
    y, s = _arrays(y_true, scores)
    k = max(1, min(int(k), y.size))
    top = np.argsort(-s)[:k]
    tp = int(y[top].sum())
    return float("inf") if tp == 0 else float(k / tp)


def recall_on_known_cases(
    y_true: Sequence, scores: Sequence, threshold: float, known_positive_idx: Optional[Iterable[int]] = None
) -> float:
    """Recall on a set of known historical fraud cases at a given alert threshold."""
    y, s = _arrays(y_true, scores)
    if known_positive_idx is None:
        known = np.flatnonzero(y == 1)
    else:
        known = np.asarray(list(known_positive_idx), dtype=int)
    if known.size == 0:
        return 0.0
    return float((s[known] >= threshold).mean())


def time_to_detection(
    scores: Sequence, timestamps: Sequence, fraud_onset_idx: int, threshold: float
) -> Optional[float]:
    """Seconds from fraud onset to the first score crossing the threshold (None if never)."""
    s = np.asarray(scores, dtype=float).ravel()
    ts = np.asarray(timestamps, dtype="datetime64[s]")
    after = np.arange(fraud_onset_idx, s.size)
    fired = after[s[after] >= threshold]
    if fired.size == 0:
        return None
    return float((ts[fired[0]] - ts[fraud_onset_idx]) / np.timedelta64(1, "s"))


# --------------------------------------------------------------------------- #
# Time-series range-aware metrics (Tatbul et al. 2018) — NEVER point-adjust   #
# --------------------------------------------------------------------------- #
def ranges_from_labels(y: Sequence) -> list[tuple[int, int]]:
    """Contiguous [start, end) anomaly ranges from a 0/1 label vector."""
    arr = np.asarray(y).astype(int).ravel()
    ranges: list[tuple[int, int]] = []
    start: Optional[int] = None
    for i, v in enumerate(arr):
        if v and start is None:
            start = i
        elif not v and start is not None:
            ranges.append((start, i))
            start = None
    if start is not None:
        ranges.append((start, arr.size))
    return ranges


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def range_based_recall(real: Sequence, pred: Sequence, alpha: float = 0.2) -> float:
    """Range-based recall: existence reward (alpha) + overlap reward (1-alpha)."""
    real_r = ranges_from_labels(real)
    pred_r = ranges_from_labels(pred)
    if not real_r:
        return 1.0 if not pred_r else 0.0
    total = 0.0
    for r in real_r:
        exists = 1.0 if any(_overlap(r, p) > 0 for p in pred_r) else 0.0
        covered = sum(_overlap(r, p) for p in pred_r)
        overlap_reward = covered / max(1, (r[1] - r[0]))
        total += alpha * exists + (1 - alpha) * min(1.0, overlap_reward)
    return float(total / len(real_r))


def range_based_precision(real: Sequence, pred: Sequence) -> float:
    """Range-based precision: fraction of predicted-anomaly length overlapping real ranges."""
    real_r = ranges_from_labels(real)
    pred_r = ranges_from_labels(pred)
    pred_len = sum(p[1] - p[0] for p in pred_r)
    if pred_len == 0:
        return 1.0 if not real_r else 0.0
    covered = sum(_overlap(p, r) for p in pred_r for r in real_r)
    return float(covered / pred_len)


def affiliation_pr(y_true: Sequence, scores: Sequence, threshold: float) -> dict[str, float]:
    """Affiliation-style PR at a threshold (range precision/recall of thresholded scores)."""
    y, s = _arrays(y_true, scores)
    pred = (s >= threshold).astype(int)
    p = range_based_precision(y, pred)
    r = range_based_recall(y, pred)
    f1 = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
    return {"range_precision": p, "range_recall": r, "range_f1": f1}


def vus_pr(y_true: Sequence, scores: Sequence, max_buffer: int = 5) -> float:
    """VUS-PR: average AUPRC as the true-label window is dilated by 0..max_buffer.

    Robust to small localisation errors (Paparrizos et al. 2022) without the
    pathologies of point-adjust. buffer=0 reduces to plain average precision.
    """
    y, s = _arrays(y_true, scores)
    aps = []
    for b in range(max_buffer + 1):
        yb = _dilate(y, b)
        aps.append(average_precision(yb, s))
    return float(np.mean(aps))


def _dilate(y: np.ndarray, buffer: int) -> np.ndarray:
    if buffer <= 0:
        return y
    out = y.copy()
    pos = np.flatnonzero(y == 1)
    for i in pos:
        lo, hi = max(0, i - buffer), min(y.size, i + buffer + 1)
        out[lo:hi] = 1
    return out


# --------------------------------------------------------------------------- #
# Comparison table — ALWAYS includes a random baseline (the §20.4 rule)       #
# --------------------------------------------------------------------------- #
@dataclass
class MetricReport:
    name: str
    average_precision: float
    precision_at_k: float
    recall_at_k: float
    alert_to_true_ratio: float
    vus_pr: float
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "average_precision": round(self.average_precision, 4),
            "precision_at_k": round(self.precision_at_k, 4),
            "recall_at_k": round(self.recall_at_k, 4),
            "alert_to_true_ratio": self.alert_to_true_ratio,
            "vus_pr": round(self.vus_pr, 4),
            **self.extra,
        }


def evaluate(y_true: Sequence, scores: Sequence, *, name: str, k: Optional[int] = None) -> MetricReport:
    """Full honest metric bundle for one scorer (no point-adjust anywhere)."""
    y, s = _arrays(y_true, scores)
    if k is None:
        k = max(1, int(y.sum()) * 2)  # default budget ~ 2x the true-positive count
    return MetricReport(
        name=name,
        average_precision=average_precision(y, s),
        precision_at_k=precision_at_k(y, s, k),
        recall_at_k=recall_at_k(y, s, k),
        alert_to_true_ratio=alert_to_true_ratio(y, s, k),
        vus_pr=vus_pr(y, s),
    )


def comparison_table(
    y_true: Sequence, scored: dict[str, Sequence], *, k: Optional[int] = None, seed: int = 1405
) -> list[dict]:
    """Compare candidate scorers; a RANDOM baseline is always injected (§20.4)."""
    y = np.asarray(y_true).astype(int).ravel()
    rng = np.random.default_rng(seed)
    table = {"__random__": rng.random(y.size), **scored}
    return [evaluate(y, s, name=name, k=k).to_dict() for name, s in table.items()]
