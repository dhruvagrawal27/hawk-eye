"""Temporal / sequence feature family (DATA-21; blueprint Part 6.6, l.254-257).

Feeds the L4 sequence layer. Every 6.6 feature over a flattened L0 DataFrame:

  * behavioural drift vs rolling baseline
  * change-point detection (mean shift in an activity series)
  * session action-sequence features (order + timing)
  * periodicity breaks (e.g. end-of-period manual journals)

All implemented in pure numpy/pandas (no ruptures/changefinder dependency).

Status: REAL (numpy/pandas only).
"""
from __future__ import annotations

import pandas as pd

E = "actor.employee_id"
VERB = "action.verb"
TS = "context.ts"
SESSION = "context.session_id"


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[TS], utc=True, errors="coerce")


def behavioural_drift(df: pd.DataFrame, window: int = 7) -> pd.Series:
    """Per-entity drift score: |recent daily-activity mean - rolling baseline mean| /
    baseline std, where the baseline is the entity's earlier history. High == drift."""
    if df.empty:
        return pd.Series(dtype=float)
    d = df.copy()
    d["_t"] = _ts(d)
    d["_day"] = d["_t"].dt.floor("D")
    out = {}
    for ent, grp in d.groupby(E):
        daily = grp.groupby("_day").size().sort_index()
        if len(daily) < window + 1:
            out[str(ent)] = 0.0
            continue
        baseline = daily.iloc[:-window]
        recent = daily.iloc[-window:]
        mu, sd = baseline.mean(), baseline.std(ddof=0)
        # If the baseline is perfectly flat (zero variance), fall back to the overall
        # series std (or 1.0) so a step change still registers as drift.
        if sd <= 1e-9:
            sd = daily.std(ddof=0) or 1.0
        out[str(ent)] = float(abs(recent.mean() - mu) / sd)
    return pd.Series(out, name="behavioural_drift")


def change_point(df: pd.DataFrame, min_len: int = 4) -> pd.DataFrame:
    """Per-entity single change-point detection on the daily-activity series via a
    cumulative-sum / max-t-stat split. Returns the change-day index and a magnitude.

    Pure-numpy: for each candidate split we compute the difference of means scaled by
    the pooled std and keep the maximum (a simple offline change-point estimator).
    """
    if df.empty:
        return pd.DataFrame(columns=["change_index", "magnitude"])
    d = df.copy()
    d["_t"] = _ts(d)
    d["_day"] = d["_t"].dt.floor("D")
    out = {}
    for ent, grp in d.groupby(E):
        series = grp.groupby("_day").size().sort_index().values.astype(float)
        n = len(series)
        if n < 2 * min_len:
            out[str(ent)] = {"change_index": -1, "magnitude": 0.0}
            continue
        best_i, best_m = -1, 0.0
        overall_sd = series.std(ddof=0) or 1.0
        for i in range(min_len, n - min_len):
            left, right = series[:i], series[i:]
            m = abs(right.mean() - left.mean()) / overall_sd
            if m > best_m:
                best_m, best_i = m, i
        out[str(ent)] = {"change_index": best_i, "magnitude": float(best_m)}
    return pd.DataFrame(out).T


def session_sequence_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-session action-sequence features: length, number of distinct verbs, mean
    inter-event seconds, and whether a 'sensitive after privileged' ordering occurs
    (a grant immediately followed by a value action within the session)."""
    if df.empty or SESSION not in df.columns:
        return pd.DataFrame()
    d = df.dropna(subset=[SESSION]).copy()
    d["_t"] = _ts(d)
    rows = {}
    for (ent, sid), grp in d.groupby([E, SESSION]):
        g = grp.sort_values("_t")
        verbs = list(g[VERB])
        gaps = g["_t"].diff().dt.total_seconds().dropna()
        risky = any(
            verbs[i] in {"grant_entitlement", "self_grant"} and
            verbs[i + 1] in {"approve_payment", "post_payment", "disburse_loan"}
            for i in range(len(verbs) - 1)
        )
        rows[(str(ent), str(sid))] = {
            "seq_len": len(verbs),
            "n_distinct_verbs": len(set(verbs)),
            "mean_gap_s": float(gaps.mean()) if len(gaps) else 0.0,
            "grant_then_value": risky,
        }
    res = pd.DataFrame(rows).T
    res.index = pd.MultiIndex.from_tuples(res.index, names=["employee", "session"])
    return res


def periodicity_break(df: pd.DataFrame, verb: str = "post_journal") -> pd.Series:
    """Per-entity flag for periodicity breaks: a burst of `verb` events concentrated at
    end-of-period (last 2 days of a month) far above the entity's other-day rate.
    Captures end-of-period manual-journal stuffing."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df[df[VERB] == verb].copy()
    if d.empty:
        return pd.Series(dtype=bool)
    d["_t"] = _ts(d)
    d["_dom"] = d["_t"].dt.day
    d["_eom"] = d["_t"].dt.days_in_month
    d["_is_eop"] = (d["_eom"] - d["_dom"]) <= 2
    out = {}
    for ent, grp in d.groupby(E):
        eop = grp["_is_eop"].mean()
        out[str(ent)] = bool(eop > 0.5 and len(grp) >= 3)
    return pd.Series(out, name="periodicity_break")


def demo_frame() -> pd.DataFrame:
    """Frame with a drifting actor and an end-of-period journal-stuffer."""
    rows = []
    base = pd.Timestamp("2026-01-01T10:00:00Z")
    # steady actor for 14 days then a spike (drift + change point)
    for day in range(14):
        n = 1 if day < 10 else 8
        for k in range(n):
            rows.append({E: "EMP-drift", VERB: "login", SESSION: f"s{day}",
                         TS: (base + pd.Timedelta(days=day, minutes=k)).strftime("%Y-%m-%dT%H:%M:%SZ")})
    # end-of-period journal stuffing
    for d_off in [29, 30, 31]:
        rows.append({E: "EMP-journal", VERB: "post_journal", SESSION: "j1",
                     TS: pd.Timestamp(f"2026-01-{d_off}T22:00:00Z").strftime("%Y-%m-%dT%H:%M:%SZ")})
    # session with grant_then_value ordering
    rows.append({E: "EMP-seq", VERB: "self_grant", SESSION: "q1", TS: "2026-01-05T03:00:00Z"})
    rows.append({E: "EMP-seq", VERB: "approve_payment", SESSION: "q1", TS: "2026-01-05T03:01:00Z"})
    return pd.DataFrame(rows)
