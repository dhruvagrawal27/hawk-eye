"""Feedback-loop fairness trap (ML-26; blueprint Part 29).

The EDD (enhanced-due-diligence) feedback loop is a fairness trap: if investigators
*confirm* (label as fraud) alerts from one group at a disproportionately higher rate than
another — whether because they're scrutinised harder, or because past alerts seeded the
training data — the model retrains on that skew and amplifies it. Over cycles the group is
over-policed regardless of true base rate.

This module monitors the **confirmation rate** (confirmed-fraud / total-dispositioned) per
group across the protected attributes, flags disproportionate confirmation, and suggests a
correction (re-weight / re-sample the labelled set so confirmation rates are comparable, or
audit the dispositions).

It is a *monitor*: it raises an alert with reason codes + narrative (Part 29.2). It never
edits labels or blocks anyone automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

import numpy as np
import pandas as pd

from ml.base.interfaces import ReasonCode

# Confirmation-rate RATIO (min/max across groups) below this flags disproportionate
# confirmation — same 4/5ths spirit as disparate impact.
DEFAULT_CONFIRMATION_RATIO_FLOOR = 0.8
# Minimum dispositioned count per group for its rate to be trusted (else pooled).
DEFAULT_MIN_GROUP = 5


@dataclass
class GroupConfirmation:
    group: str
    n_dispositioned: int
    n_confirmed: int
    confirmation_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "n_dispositioned": self.n_dispositioned,
            "n_confirmed": self.n_confirmed,
            "confirmation_rate": round(self.confirmation_rate, 4),
        }


@dataclass
class FeedbackTrapResult:
    """Confirmation-distribution analysis for ONE protected attribute."""

    attribute: str
    group_confirmation: dict[str, GroupConfirmation]
    confirmation_ratio: float
    confirmation_gap: float
    disproportionate: bool
    ratio_floor: float
    reason_codes: list[dict[str, Any]] = field(default_factory=list)
    narrative: Optional[str] = None
    suggested_correction: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attribute": self.attribute,
            "group_confirmation": {g: gc.to_dict() for g, gc in self.group_confirmation.items()},
            "confirmation_ratio": round(self.confirmation_ratio, 4),
            "confirmation_gap": round(self.confirmation_gap, 4),
            "disproportionate": self.disproportionate,
            "ratio_floor": self.ratio_floor,
            "reason_codes": self.reason_codes,
            "narrative": self.narrative,
            "suggested_correction": self.suggested_correction,
        }


def _confirmed_mask(dispositions: Iterable[Any]) -> np.ndarray:
    """Coerce dispositions to a confirmed(1)/cleared(0) mask.

    Accepts bools/0-1 ints, or strings ('confirmed'/'fraud'/'true_positive' -> 1;
    'cleared'/'false_positive'/'benign' -> 0).
    """
    confirmed_words = {"confirmed", "fraud", "true_positive", "tp", "sar", "escalated", "1", "true"}
    out = []
    for d in dispositions:
        if isinstance(d, (bool, np.bool_)):
            out.append(int(bool(d)))
        elif isinstance(d, (int, float, np.integer, np.floating)) and not isinstance(d, bool):
            out.append(int(d >= 0.5))
        else:
            out.append(1 if str(d).strip().lower() in confirmed_words else 0)
    return np.asarray(out, dtype=int)


def analyze_attribute(
    dispositions: Iterable[Any],
    sensitive: Iterable[Any],
    *,
    attribute: str = "group",
    ratio_floor: float = DEFAULT_CONFIRMATION_RATIO_FLOOR,
    min_group: int = DEFAULT_MIN_GROUP,
    narrator: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> FeedbackTrapResult:
    """Analyse confirmation distribution across groups of ONE protected attribute."""
    confirmed = _confirmed_mask(dispositions)
    grp = pd.Series([str(g) for g in sensitive])
    conf = pd.Series(confirmed, index=grp.index)

    gconf: dict[str, GroupConfirmation] = {}
    rates: list[float] = []
    for g in pd.unique(grp):
        mask = grp.values == g
        n = int(mask.sum())
        c = int(conf[mask].sum())
        rate = float(c / n) if n else 0.0
        gconf[str(g)] = GroupConfirmation(group=str(g), n_dispositioned=n, n_confirmed=c,
                                          confirmation_rate=rate)
        if n >= min_group:
            rates.append(rate)

    if len(rates) >= 2:
        hi = max(rates)
        ratio = float(min(rates) / hi) if hi > 0 else 1.0
        gap = float(hi - min(rates))
    else:
        ratio, gap = 1.0, 0.0

    disproportionate = ratio < ratio_floor and gap > 0
    result = FeedbackTrapResult(
        attribute=attribute,
        group_confirmation=gconf,
        confirmation_ratio=ratio,
        confirmation_gap=gap,
        disproportionate=disproportionate,
        ratio_floor=ratio_floor,
    )

    if disproportionate:
        if narrator is None:
            from ml.narrative import render_template as _render

            def narrator(ctx: dict[str, Any]) -> dict[str, Any]:  # type: ignore[misc]
                return {"narrative": _render(ctx), "provider": "template"}

        over = max(gconf.values(), key=lambda gc: gc.confirmation_rate)
        under = min((gc for gc in gconf.values() if gc.n_dispositioned >= min_group),
                    key=lambda gc: gc.confirmation_rate, default=over)
        rc = ReasonCode(
            source="rule",
            code=f"fairness.feedback_trap.{attribute}",
            detail=f"Disproportionate EDD confirmation across '{attribute}': group "
            f"'{over.group}' confirmed at {over.confirmation_rate:.2f} vs '{under.group}' at "
            f"{under.confirmation_rate:.2f} (ratio={ratio:.2f} < {ratio_floor:.2f}); retraining "
            f"on these labels risks amplifying the skew.",
            contribution=float(gap),
        )
        result.reason_codes = [rc.to_dict()]
        result.suggested_correction = suggest_correction(result)
        ctx = {
            "alert_id": f"feedback-trap-{attribute}",
            "entity_id": attribute,
            "risk_score": min(100, int(round((1.0 - ratio) * 100))),
            "severity": "high",
            "reason_codes": result.reason_codes,
        }
        result.narrative = narrator(ctx).get("narrative")
    return result


def suggest_correction(result: FeedbackTrapResult) -> dict[str, Any]:
    """Suggest a re-weighting that equalises confirmation rates across groups.

    Computes per-group sample weights = target_rate / group_rate so the labelled set, when
    retrained on, no longer over-represents the over-confirmed group. Pure suggestion — the
    caller (training pipeline / governance) decides whether to apply it.
    """
    rates = {g: gc.confirmation_rate for g, gc in result.group_confirmation.items()
             if gc.n_dispositioned > 0}
    if not rates:
        return {"method": "reweight", "weights": {}, "note": "no dispositioned samples"}
    target = float(np.mean(list(rates.values())))
    weights = {g: float(target / r) if r > 0 else 1.0 for g, r in rates.items()}
    return {
        "method": "reweight_or_resample_labels",
        "target_confirmation_rate": round(target, 4),
        "group_weights": {g: round(w, 4) for g, w in weights.items()},
        "note": "Down-weight over-confirmed groups (or audit their dispositions) before retraining "
        "to avoid amplifying confirmation bias; also recommend randomized review sampling.",
    }


def detect_feedback_trap(
    dispositions: Iterable[Any],
    protected: pd.DataFrame,
    *,
    ratio_floor: float = DEFAULT_CONFIRMATION_RATIO_FLOOR,
    min_group: int = DEFAULT_MIN_GROUP,
    attributes: Optional[Iterable[str]] = None,
    narrator: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> dict[str, FeedbackTrapResult]:
    """Run the feedback-trap monitor across every protected attribute in ``protected``."""
    from ml.fairness.metrics import PROTECTED_ATTRIBUTES, _bin_if_continuous

    attrs = list(attributes) if attributes is not None else [
        c for c in protected.columns if c in PROTECTED_ATTRIBUTES or c in protected.columns
    ]
    out: dict[str, FeedbackTrapResult] = {}
    for attr in attrs:
        if attr not in protected.columns:
            continue
        groups = _bin_if_continuous(protected[attr], attr)
        out[attr] = analyze_attribute(
            dispositions, groups, attribute=attr, ratio_floor=ratio_floor,
            min_group=min_group, narrator=narrator,
        )
    return out


def feedback_trap_alerts(results: dict[str, FeedbackTrapResult]) -> list[dict[str, Any]]:
    """Collect only the attributes where disproportionate confirmation was detected."""
    return [r.to_dict() for r in results.values() if r.disproportionate]
