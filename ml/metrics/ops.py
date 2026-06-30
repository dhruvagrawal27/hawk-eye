"""Operational + business metrics (ML-29 / blueprint Part 14).

Pure functions over plain Python / numpy inputs. No I/O, no global state.

Conventions
-----------
* Durations are accepted either as already-computed numeric values (in a stated
  unit) or as pairs of timestamps; helpers normalise to a numeric unit.
* "Alert volume vs analyst capacity" is reported as a utilisation ratio plus a
  backlog count so a dashboard can show both headroom and overflow.
* RBI TAT compliance is the fraction of *closed-or-eligible* cases dispositioned
  within the regulatory turnaround time (default 30 days). This is the metric
  the blueprint calls out explicitly (Part 14, operational family).

These metrics are ALERT-ONLY observability — they never gate or block anything.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence, Union

import numpy as np
import pandas as pd

# A duration may be given as a number (in the function's stated unit), a
# timedelta, or a numpy timedelta64.
Duration = Union[float, int, timedelta, np.timedelta64]
# A timestamp may be a datetime, pandas Timestamp, numpy datetime64, or
# ISO-8601 string.
TimeLike = Union[str, datetime, pd.Timestamp, np.datetime64]


# --------------------------------------------------------------------------- #
# internal normalisers                                                        #
# --------------------------------------------------------------------------- #
def _to_seconds(d: Duration) -> float:
    """Coerce a duration to seconds. Bare numbers are assumed already in seconds."""
    if isinstance(d, np.timedelta64):
        return float(d / np.timedelta64(1, "s"))
    if isinstance(d, timedelta):
        return d.total_seconds()
    return float(d)


def _to_days(d: Duration) -> float:
    """Coerce a duration to days. Bare numbers are assumed already in days."""
    if isinstance(d, (np.timedelta64, timedelta)):
        return _to_seconds(d) / 86400.0
    return float(d)


def _ts(t: TimeLike) -> pd.Timestamp:
    return pd.Timestamp(t)


# --------------------------------------------------------------------------- #
# Operational metrics                                                         #
# --------------------------------------------------------------------------- #
def alert_volume_vs_capacity(
    n_alerts: int,
    analyst_capacity: int,
    *,
    period_label: str = "day",
) -> dict:
    """Alert volume measured against analyst review capacity for a period.

    Parameters
    ----------
    n_alerts:
        Number of alerts surfaced in the period.
    analyst_capacity:
        Number of alerts the analyst pool can disposition in the same period.
    period_label:
        Free-text label for the period (e.g. ``"day"``, ``"shift"``) — carried
        through for dashboard display only.

    Returns
    -------
    dict with ``n_alerts``, ``capacity``, ``utilization`` (alerts / capacity;
    ``inf`` if capacity is 0 and alerts > 0, ``0.0`` if both 0),
    ``backlog`` (alerts that cannot be handled this period, ``>=0``),
    ``within_capacity`` (bool) and ``period``.
    """
    n_alerts = int(n_alerts)
    capacity = int(analyst_capacity)
    if n_alerts < 0 or capacity < 0:
        raise ValueError("n_alerts and analyst_capacity must be non-negative")
    if capacity == 0:
        utilization = 0.0 if n_alerts == 0 else float("inf")
    else:
        utilization = n_alerts / capacity
    backlog = max(0, n_alerts - capacity)
    return {
        "n_alerts": n_alerts,
        "capacity": capacity,
        "utilization": utilization,
        "backlog": backlog,
        "within_capacity": n_alerts <= capacity,
        "period": period_label,
    }


def mean_time_to_detection(
    onset_times: Optional[Sequence[TimeLike]] = None,
    detection_times: Optional[Sequence[TimeLike]] = None,
    *,
    durations: Optional[Sequence[Duration]] = None,
    unit: str = "hours",
) -> float:
    """Mean time-to-detection (MTTD): fraud-onset -> first-detection latency.

    Provide EITHER paired ``onset_times``/``detection_times`` (timestamps), OR a
    pre-computed ``durations`` sequence. Undetected cases should be omitted by
    the caller (a ``None`` detection time is dropped) — MTTD is conditioned on
    detection; coverage is reported separately via recall metrics.

    Returns the mean latency in ``unit`` (``"seconds"``, ``"minutes"``,
    ``"hours"`` or ``"days"``). Returns ``nan`` when there is nothing to average.
    """
    divisor = {"seconds": 1.0, "minutes": 60.0, "hours": 3600.0, "days": 86400.0}
    if unit not in divisor:
        raise ValueError(f"unit must be one of {sorted(divisor)}")
    secs: list[float] = []
    if durations is not None:
        secs = [_to_seconds(d) for d in durations if d is not None]
    else:
        if onset_times is None or detection_times is None:
            raise ValueError(
                "provide either durations, or both onset_times and detection_times"
            )
        if len(onset_times) != len(detection_times):
            raise ValueError("onset_times and detection_times must be the same length")
        for o, d in zip(onset_times, detection_times):
            if o is None or d is None:
                continue
            secs.append((_ts(d) - _ts(o)).total_seconds())
    if not secs:
        return float("nan")
    return float(np.mean(secs) / divisor[unit])


def mean_time_to_disposition(
    alert_times: Optional[Sequence[TimeLike]] = None,
    disposition_times: Optional[Sequence[TimeLike]] = None,
    *,
    durations: Optional[Sequence[Duration]] = None,
    unit: str = "days",
) -> float:
    """Mean time-to-disposition: alert-created -> investigator-dispositioned.

    Same calling convention as :func:`mean_time_to_detection`. Open cases (no
    disposition time) are dropped. Returns the mean in ``unit`` (default days),
    ``nan`` when empty.
    """
    return mean_time_to_detection(
        alert_times, disposition_times, durations=durations, unit=unit
    )


def false_positive_rate(
    y_true: Optional[Sequence] = None,
    y_alert: Optional[Sequence] = None,
    *,
    false_positives: Optional[int] = None,
    true_negatives: Optional[int] = None,
) -> float:
    """False-positive rate = FP / (FP + TN).

    Provide EITHER label/alert vectors (``y_true``, ``y_alert`` of 0/1), OR the
    raw ``false_positives`` and ``true_negatives`` counts. FPR is the share of
    *truly-benign* entities that nonetheless raised an alert — the operational
    cost driver. Returns ``nan`` when there are no benign cases (FP+TN == 0).
    """
    if false_positives is not None or true_negatives is not None:
        if false_positives is None or true_negatives is None:
            raise ValueError("provide both false_positives and true_negatives")
        fp, tn = int(false_positives), int(true_negatives)
    else:
        if y_true is None or y_alert is None:
            raise ValueError("provide either count args, or y_true and y_alert")
        yt = np.asarray(y_true).astype(int).ravel()
        ya = np.asarray(y_alert).astype(int).ravel()
        if yt.shape != ya.shape:
            raise ValueError("y_true and y_alert must be the same length")
        benign = yt == 0
        fp = int(np.sum(benign & (ya == 1)))
        tn = int(np.sum(benign & (ya == 0)))
    denom = fp + tn
    if denom == 0:
        return float("nan")
    return fp / denom


def rbi_tat_compliance(
    case_durations: Optional[Sequence[Duration]] = None,
    *,
    opened_times: Optional[Sequence[TimeLike]] = None,
    closed_times: Optional[Sequence[TimeLike]] = None,
    tat_days: float = 30.0,
    count_open_as_breach: bool = True,
) -> dict:
    """RBI turnaround-time (TAT) compliance: fraction dispositioned within ``tat_days``.

    RBI guidance requires fraud cases to be dispositioned within 30 days; this
    metric is the fraction of cases closed within that window.

    Provide EITHER ``case_durations`` (numeric days or timedeltas), OR paired
    ``opened_times``/``closed_times`` timestamps. A ``None`` closed time means
    the case is still open: if ``count_open_as_breach`` is True (default,
    conservative) an open case past ``tat_days`` counts as a breach and an open
    case still within the window is counted as compliant-so-far; if False, open
    cases are excluded from the denominator entirely.

    Returns a dict with ``compliance`` (fraction in [0,1], ``nan`` if no cases
    counted), ``n_cases``, ``n_within``, ``n_breached``, ``n_open_excluded`` and
    ``tat_days``.
    """
    if tat_days <= 0:
        raise ValueError("tat_days must be positive")

    days_list: list[Optional[float]] = []
    if case_durations is not None:
        days_list = [None if d is None else _to_days(d) for d in case_durations]
    else:
        if opened_times is None or closed_times is None:
            raise ValueError(
                "provide either case_durations, or both opened_times and closed_times"
            )
        if len(opened_times) != len(closed_times):
            raise ValueError("opened_times and closed_times must be the same length")
        now = pd.Timestamp.utcnow().tz_localize(None)
        for o, c in zip(opened_times, closed_times):
            if o is None:
                days_list.append(None)
                continue
            if c is None:
                # open case: elapsed-so-far against now
                elapsed = (
                    now - _ts(o).tz_localize(None) if _ts(o).tzinfo else now - _ts(o)
                ).total_seconds() / 86400.0
                days_list.append(("open", elapsed))  # type: ignore[arg-type]
            else:
                days_list.append((_ts(c) - _ts(o)).total_seconds() / 86400.0)

    n_within = 0
    n_breached = 0
    n_open_excluded = 0
    for item in days_list:
        if item is None:
            continue
        is_open = isinstance(item, tuple)
        elapsed = item[1] if is_open else float(item)  # type: ignore[index]
        if is_open and not count_open_as_breach:
            n_open_excluded += 1
            continue
        if is_open:
            # open case: compliant only if still within window, else breach
            if elapsed <= tat_days:
                n_within += 1
            else:
                n_breached += 1
        else:
            if elapsed <= tat_days:
                n_within += 1
            else:
                n_breached += 1

    n_cases = n_within + n_breached
    compliance = (n_within / n_cases) if n_cases > 0 else float("nan")
    return {
        "compliance": compliance,
        "n_cases": n_cases,
        "n_within": n_within,
        "n_breached": n_breached,
        "n_open_excluded": n_open_excluded,
        "tat_days": float(tat_days),
    }


# --------------------------------------------------------------------------- #
# Business metrics                                                            #
# --------------------------------------------------------------------------- #
def estimated_loss_avoided(
    exposures: Sequence[float],
    *,
    detected: Optional[Sequence[bool]] = None,
    recovery_rate: float = 1.0,
    currency: str = "INR",
) -> dict:
    """Estimated loss avoided by detected-and-stopped fraud.

    Parameters
    ----------
    exposures:
        Monetary exposure per (true-fraud) case. Use the at-risk amount, e.g.
        ``object.amount`` for the worked burst (4_800_000 INR).
    detected:
        Optional 0/1 / bool mask aligned to ``exposures``; only detected cases
        contribute to loss avoided. If omitted, all exposures are assumed
        detected-and-avoided.
    recovery_rate:
        Fraction of a detected exposure actually prevented/recovered (0..1).
        Models the reality that detection rarely recovers 100%.

    Returns dict with ``loss_avoided``, ``total_exposure``, ``detected_exposure``,
    ``n_cases``, ``n_detected``, ``recovery_rate`` and ``currency``.
    """
    if not 0.0 <= recovery_rate <= 1.0:
        raise ValueError("recovery_rate must be in [0, 1]")
    exp = np.asarray(exposures, dtype=float).ravel()
    total = float(np.nansum(exp))
    if detected is None:
        mask = np.ones(exp.shape, dtype=bool)
    else:
        mask = np.asarray(detected).astype(bool).ravel()
        if mask.shape != exp.shape:
            raise ValueError("detected must be the same length as exposures")
    detected_exposure = float(np.nansum(exp[mask]))
    return {
        "loss_avoided": detected_exposure * recovery_rate,
        "total_exposure": total,
        "detected_exposure": detected_exposure,
        "n_cases": int(exp.size),
        "n_detected": int(np.sum(mask)),
        "recovery_rate": float(recovery_rate),
        "currency": currency,
    }


def cases_surfaced_system_vs_tips(
    source: Optional[Sequence[str]] = None,
    *,
    n_system: Optional[int] = None,
    n_tips: Optional[int] = None,
    system_labels: Iterable[str] = ("system", "model", "ml", "alert"),
) -> dict:
    """Attribution of true cases to the ML system vs human tips/whistleblowers.

    Provide EITHER a ``source`` sequence (one label per surfaced case), OR the
    pre-aggregated ``n_system`` / ``n_tips`` counts. Anything in ``source`` not
    matching ``system_labels`` (case-insensitive) is bucketed as a tip.

    Returns dict with ``n_system``, ``n_tips``, ``total`` and ``system_share``
    (system / total; ``nan`` if total is 0). A healthy program shifts share
    toward the system over time.
    """
    if n_system is not None or n_tips is not None:
        if n_system is None or n_tips is None:
            raise ValueError("provide both n_system and n_tips")
        sys_n, tip_n = int(n_system), int(n_tips)
    else:
        if source is None:
            raise ValueError("provide either source, or both n_system and n_tips")
        labels = {s.lower() for s in system_labels}
        sys_n = sum(1 for s in source if str(s).lower() in labels)
        tip_n = sum(1 for s in source if str(s).lower() not in labels)
    total = sys_n + tip_n
    share = (sys_n / total) if total > 0 else float("nan")
    return {
        "n_system": sys_n,
        "n_tips": tip_n,
        "total": total,
        "system_share": share,
    }


# --------------------------------------------------------------------------- #
# Dashboard aggregator                                                        #
# --------------------------------------------------------------------------- #
@dataclass
class OpsDashboard:
    """Container for the full operational + business metric panel."""

    alert_volume: dict
    mttd: float
    mttd_unit: str
    mean_time_to_disposition: float
    disposition_unit: str
    false_positive_rate: float
    rbi_tat_compliance: dict
    estimated_loss_avoided: dict
    cases_system_vs_tips: dict

    def to_dict(self) -> dict:
        return asdict(self)


def compute_ops_dashboard(
    *,
    n_alerts: int,
    analyst_capacity: int,
    detection_durations: Optional[Sequence[Duration]] = None,
    detection_onset_times: Optional[Sequence[TimeLike]] = None,
    detection_times: Optional[Sequence[TimeLike]] = None,
    mttd_unit: str = "hours",
    disposition_durations: Optional[Sequence[Duration]] = None,
    alert_times: Optional[Sequence[TimeLike]] = None,
    disposition_times: Optional[Sequence[TimeLike]] = None,
    disposition_unit: str = "days",
    y_true: Optional[Sequence] = None,
    y_alert: Optional[Sequence] = None,
    false_positives: Optional[int] = None,
    true_negatives: Optional[int] = None,
    case_durations: Optional[Sequence[Duration]] = None,
    opened_times: Optional[Sequence[TimeLike]] = None,
    closed_times: Optional[Sequence[TimeLike]] = None,
    tat_days: float = 30.0,
    exposures: Optional[Sequence[float]] = None,
    detected: Optional[Sequence[bool]] = None,
    recovery_rate: float = 1.0,
    currency: str = "INR",
    case_source: Optional[Sequence[str]] = None,
    n_system: Optional[int] = None,
    n_tips: Optional[int] = None,
    period_label: str = "day",
) -> dict:
    """Compute every operational + business metric and return them as one dict.

    This is the single entry point a monitoring job / governance report calls.
    Each sub-metric accepts the same EITHER/OR inputs as its standalone
    function; pass whichever form you have (timestamps vs pre-computed
    durations vs aggregate counts). Sub-metrics whose inputs are entirely
    absent fall back to safe empty results (``nan``/empty dicts) rather than
    raising, so a partial dashboard still renders.

    Returns a plain ``dict`` (also available structured via
    :class:`OpsDashboard` ``.to_dict()``).
    """
    alert_volume = alert_volume_vs_capacity(
        n_alerts, analyst_capacity, period_label=period_label
    )

    if detection_durations is not None or (
        detection_onset_times is not None and detection_times is not None
    ):
        mttd = mean_time_to_detection(
            detection_onset_times,
            detection_times,
            durations=detection_durations,
            unit=mttd_unit,
        )
    else:
        mttd = float("nan")

    if disposition_durations is not None or (
        alert_times is not None and disposition_times is not None
    ):
        mttdisp = mean_time_to_disposition(
            alert_times,
            disposition_times,
            durations=disposition_durations,
            unit=disposition_unit,
        )
    else:
        mttdisp = float("nan")

    if (y_true is not None and y_alert is not None) or (
        false_positives is not None and true_negatives is not None
    ):
        fpr = false_positive_rate(
            y_true,
            y_alert,
            false_positives=false_positives,
            true_negatives=true_negatives,
        )
    else:
        fpr = float("nan")

    if case_durations is not None or (
        opened_times is not None and closed_times is not None
    ):
        tat = rbi_tat_compliance(
            case_durations,
            opened_times=opened_times,
            closed_times=closed_times,
            tat_days=tat_days,
        )
    else:
        tat = rbi_tat_compliance(case_durations=[], tat_days=tat_days)

    if exposures is not None:
        loss = estimated_loss_avoided(
            exposures, detected=detected, recovery_rate=recovery_rate, currency=currency
        )
    else:
        loss = estimated_loss_avoided(
            [], recovery_rate=recovery_rate, currency=currency
        )

    if case_source is not None or (n_system is not None and n_tips is not None):
        cstv = cases_surfaced_system_vs_tips(
            case_source, n_system=n_system, n_tips=n_tips
        )
    else:
        cstv = cases_surfaced_system_vs_tips(n_system=0, n_tips=0)

    dash = OpsDashboard(
        alert_volume=alert_volume,
        mttd=mttd,
        mttd_unit=mttd_unit,
        mean_time_to_disposition=mttdisp,
        disposition_unit=disposition_unit,
        false_positive_rate=fpr,
        rbi_tat_compliance=tat,
        estimated_loss_avoided=loss,
        cases_system_vs_tips=cstv,
    )
    return dash.to_dict()
