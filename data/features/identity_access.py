"""Identity / access feature family (DATA-20; blueprint Part 6.1, l.216-222).

Every 6.1 feature, each a pure function over a flattened-L0 DataFrame returning a
per-entity pandas Series (index = employee_id) keyed with `feature_key()` where a
single scalar/name is needed. Features implemented:

  * off-hours / odd-hours score (vs personal & peer) + first-time-after-hours flag
  * login velocity (logins per hour)
  * failed -> success bursts
  * impossible-travel (geo change faster than physically possible)
  * new-device / new-geo
  * dormant-account reactivation -> activity
  * privilege-escalation events
  * entitlement-change velocity
  * acting-outside-role (peer deviation in verb mix)
  * session-duration anomaly
  * concurrent-session anomaly
  * "no-leave-taken" streak

Status: REAL (numpy/pandas only).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from data.config import feature_key

E = "actor.employee_id"
PEER = "actor.peer_group"
VERB = "action.verb"
TS = "context.ts"
OFFH = "context.is_off_hours"
GEO = "context.geo"
DEVICE = "context.device"
SESSION = "context.session_id"

# verbs that represent a privilege escalation / entitlement change
ESCALATION_VERBS = {"grant_entitlement", "privilege_escalation", "role_change", "self_grant"}
LOGIN_OK = "login"
LOGIN_FAIL = "login_failed"


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[TS], utc=True, errors="coerce")


def offhours_score(df: pd.DataFrame, window: str = "all") -> pd.Series:
    """Per-entity fraction of events that occur off-hours, scored vs the peer mean.

    Returns a Series (index=employee_id) of (personal_rate - peer_rate); >0 means the
    employee is more nocturnal than peers. The personal_rate alone is also a feature.
    """
    if df.empty or OFFH not in df.columns:
        return pd.Series(dtype=float)
    d = df.copy()
    d["_off"] = d[OFFH].fillna(False).astype(bool).astype(float)
    personal = d.groupby(E)["_off"].mean()
    if PEER in d.columns:
        peer_rate = d.groupby(PEER)["_off"].mean()
        ent_peer = d.groupby(E)[PEER].first()
        peer_for_ent = ent_peer.map(peer_rate)
        score = personal - peer_for_ent.fillna(personal.mean())
    else:
        score = personal - personal.mean()
    score.index = [str(i) for i in score.index]
    return score.rename(feature_key("<entity>", "offhours_score", window))


def first_time_after_hours(df: pd.DataFrame) -> pd.Series:
    """Boolean per-entity: True if this entity has an off-hours event but the bulk of
    their history is on-hours (a first/rare after-hours appearance)."""
    if df.empty or OFFH not in df.columns:
        return pd.Series(dtype=bool)
    d = df.copy()
    d["_off"] = d[OFFH].fillna(False).astype(bool)
    rate = d.groupby(E)["_off"].mean()
    has_off = d.groupby(E)["_off"].any()
    return (has_off & (rate < 0.4)).rename("first_time_after_hours")


def login_velocity(df: pd.DataFrame, window_minutes: int = 60) -> pd.Series:
    """Max number of login events in any rolling `window_minutes` per entity."""
    if df.empty:
        return pd.Series(dtype=float)
    d = df[df[VERB].isin([LOGIN_OK, LOGIN_FAIL])].copy()
    if d.empty:
        return pd.Series(dtype=float)
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        t = grp["_t"].sort_values().dropna()
        if len(t) <= 1:
            out[str(ent)] = float(len(t))
            continue
        s = pd.Series(1, index=t)
        roll = s.rolling(f"{window_minutes}min").sum()
        out[str(ent)] = float(roll.max())
    return pd.Series(out, name=f"login_velocity_{window_minutes}m")


def failed_then_success_burst(df: pd.DataFrame, min_fails: int = 3, window_minutes: int = 10) -> pd.Series:
    """Per-entity count of (>=min_fails failed logins followed by a success) bursts —
    a credential-stuffing / brute-force-then-in signature."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin([LOGIN_OK, LOGIN_FAIL])].copy()
    if d.empty:
        return pd.Series(dtype=int)
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        g = grp.sort_values("_t")
        fails = 0
        last_fail_t = None
        bursts = 0
        for _, r in g.iterrows():
            if r[VERB] == LOGIN_FAIL:
                fails += 1
                last_fail_t = r["_t"]
            elif r[VERB] == LOGIN_OK:
                if fails >= min_fails and last_fail_t is not None and \
                        (r["_t"] - last_fail_t) <= pd.Timedelta(minutes=window_minutes):
                    bursts += 1
                fails = 0
                last_fail_t = None
        out[str(ent)] = bursts
    return pd.Series(out, name="failed_then_success_burst")


# rough km between a few seeded geos; unknown pairs treated as "far"
_GEO_KM = {
    ("Mumbai", "Delhi"): 1150, ("Mumbai", "London"): 7200, ("Delhi", "London"): 6700,
    ("Mumbai", "Chennai"): 1030, ("Mumbai", "Mumbai"): 0, ("Delhi", "Delhi"): 0,
}


def _geo_dist_km(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return float(_GEO_KM.get((a, b)) or _GEO_KM.get((b, a)) or 8000.0)


def impossible_travel(df: pd.DataFrame, max_speed_kmh: float = 900.0) -> pd.Series:
    """Per-entity count of consecutive events whose geo change implies speed >
    `max_speed_kmh` (commercial jet) — i.e. physically impossible travel."""
    if df.empty or GEO not in df.columns:
        return pd.Series(dtype=int)
    d = df.copy()
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        g = grp.dropna(subset=[GEO]).sort_values("_t")
        cnt = 0
        prev_geo = prev_t = None
        for _, r in g.iterrows():
            if prev_geo is not None and r[GEO] != prev_geo:
                dt_h = (r["_t"] - prev_t).total_seconds() / 3600.0
                km = _geo_dist_km(str(prev_geo), str(r[GEO]))
                if dt_h >= 0 and (dt_h == 0 and km > 0 or (dt_h > 0 and km / dt_h > max_speed_kmh)):
                    cnt += 1
            prev_geo, prev_t = r[GEO], r["_t"]
        out[str(ent)] = cnt
    return pd.Series(out, name="impossible_travel")


def new_device_or_geo(df: pd.DataFrame) -> pd.DataFrame:
    """Per-entity counts of distinct devices and geos, plus a `new_device`/`new_geo`
    flag (>1 distinct => the entity used something other than their habitual one)."""
    if df.empty:
        return pd.DataFrame()
    agg = {}
    if DEVICE in df.columns:
        agg["n_devices"] = df.groupby(E)[DEVICE].nunique()
    if GEO in df.columns:
        agg["n_geos"] = df.groupby(E)[GEO].nunique()
    out = pd.DataFrame(agg)
    if "n_devices" in out:
        out["new_device"] = out["n_devices"] > 1
    if "n_geos" in out:
        out["new_geo"] = out["n_geos"] > 1
    return out


def dormant_reactivation(df: pd.DataFrame, dormant_days: int = 30) -> pd.Series:
    """Per-entity flag: a gap of >= `dormant_days` between two events (account went
    dormant then reactivated to activity)."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df.copy()
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        t = grp["_t"].dropna().sort_values()
        if len(t) < 2:
            out[str(ent)] = False
            continue
        gap = t.diff().max()
        out[str(ent)] = bool(gap >= pd.Timedelta(days=dormant_days))
    return pd.Series(out, name="dormant_reactivation")


def privilege_escalation(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of privilege-escalation / entitlement-grant verbs."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(ESCALATION_VERBS)]
    return d.groupby(E).size().reindex(df[E].unique(), fill_value=0).rename("privilege_escalation")


def entitlement_change_velocity(df: pd.DataFrame, window_days: int = 7) -> pd.Series:
    """Max entitlement-changing events in any rolling `window_days` per entity."""
    if df.empty:
        return pd.Series(dtype=float)
    d = df[df[VERB].isin(ESCALATION_VERBS)].copy()
    if d.empty:
        return pd.Series(dtype=float)
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        t = grp["_t"].dropna().sort_values()
        if len(t) <= 1:
            out[str(ent)] = float(len(t))
            continue
        s = pd.Series(1, index=t)
        out[str(ent)] = float(s.rolling(f"{window_days}D").sum().max())
    return pd.Series(out, name=f"entitlement_change_velocity_{window_days}d")


def acting_outside_role(df: pd.DataFrame) -> pd.Series:
    """Per-entity deviation of verb-mix from the peer-group norm (L1 distance over the
    verb distribution). High => acting outside their role's normal action profile."""
    if df.empty or PEER not in df.columns:
        return pd.Series(dtype=float)
    d = df.copy()
    # verb distribution per entity and per peer group
    ent_mix = d.groupby([E, VERB]).size().unstack(fill_value=0)
    ent_mix = ent_mix.div(ent_mix.sum(axis=1), axis=0)
    ent_peer = d.groupby(E)[PEER].first()
    peer_mix = d.groupby([PEER, VERB]).size().unstack(fill_value=0)
    peer_mix = peer_mix.div(peer_mix.sum(axis=1), axis=0)
    out = {}
    for ent in ent_mix.index:
        peer = ent_peer.get(ent)
        if peer is None or peer not in peer_mix.index:
            out[str(ent)] = 0.0
            continue
        diff = (ent_mix.loc[ent] - peer_mix.loc[peer]).abs().sum()
        out[str(ent)] = float(diff)
    return pd.Series(out, name="acting_outside_role")


def session_duration_anomaly(df: pd.DataFrame) -> pd.Series:
    """Per-entity z-score of mean session duration vs the population (sessions inferred
    from min..max event ts per session_id)."""
    if df.empty or SESSION not in df.columns:
        return pd.Series(dtype=float)
    d = df.copy()
    d["_t"] = _ts(d)
    dur = d.dropna(subset=[SESSION]).groupby([E, SESSION])["_t"].agg(["min", "max"])
    dur["secs"] = (dur["max"] - dur["min"]).dt.total_seconds()
    ent_mean = dur.groupby(level=0)["secs"].mean()
    if ent_mean.std(ddof=0) < 1e-9:
        return pd.Series(0.0, index=[str(i) for i in ent_mean.index], name="session_duration_anomaly")
    z = (ent_mean - ent_mean.mean()) / ent_mean.std(ddof=0)
    z.index = [str(i) for i in z.index]
    return z.rename("session_duration_anomaly")


def concurrent_session_anomaly(df: pd.DataFrame) -> pd.Series:
    """Per-entity max number of overlapping sessions active at the same time."""
    if df.empty or SESSION not in df.columns:
        return pd.Series(dtype=int)
    d = df.copy()
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        spans = grp.dropna(subset=[SESSION]).groupby(SESSION)["_t"].agg(["min", "max"]).dropna()
        if spans.empty:
            out[str(ent)] = 0
            continue
        # sweep line over interval starts/ends
        events = []
        for _, r in spans.iterrows():
            events.append((r["min"], 1))
            events.append((r["max"], -1))
        events.sort(key=lambda x: (x[0], -x[1]))
        cur = mx = 0
        for _, delta in events:
            cur += delta
            mx = max(mx, cur)
        out[str(ent)] = int(mx)
    return pd.Series(out, name="concurrent_session_anomaly")


def no_leave_taken_streak(df: pd.DataFrame, leave_verb: str = "leave") -> pd.Series:
    """Per-entity number of distinct active days with NO `leave` event — the rogue-trader
    "never takes a holiday" signal. Higher streak == more suspicious."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df.copy()
    d["_t"] = _ts(d)
    d["_day"] = d["_t"].dt.date
    took_leave = d[d[VERB] == leave_verb].groupby(E)["_day"].nunique()
    active_days = d.groupby(E)["_day"].nunique()
    streak = active_days.sub(took_leave, fill_value=0).clip(lower=0).astype(int)
    streak.index = [str(i) for i in streak.index]
    return streak.rename("no_leave_taken_streak")


def demo_frame() -> pd.DataFrame:
    """Tiny frame mixing a benign and an anomalous identity/access actor."""
    rows = []
    base = pd.Timestamp("2026-01-01T09:00:00Z")
    # benign teller: on-hours, single device/geo, takes leave
    for i in range(10):
        rows.append({E: "EMP-good", PEER: "PG-teller", VERB: "login",
                     TS: (base + pd.Timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     OFFH: False, GEO: "Mumbai", DEVICE: "WS-1", SESSION: f"s{i}"})
    rows.append({E: "EMP-good", PEER: "PG-teller", VERB: "leave",
                 TS: (base + pd.Timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 OFFH: False, GEO: "Mumbai", DEVICE: "WS-1", SESSION: "sL"})
    # anomalous: mostly on-hours history (so off-hours is a FIRST/rare appearance),
    # then impossible travel, dormant reactivation, escalation, no leave.
    for i in range(10):
        rows.append({E: "EMP-bad", PEER: "PG-teller", VERB: "login",
                     TS: (base + pd.Timedelta(days=i, hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     OFFH: False, GEO: "Mumbai", DEVICE: "WS-9", SESSION: f"bn{i}"})
    # the rare off-hours burst with impossible travel
    rows.append({E: "EMP-bad", PEER: "PG-teller", VERB: "login",
                 TS: "2026-01-15T02:00:00Z", OFFH: True, GEO: "Mumbai", DEVICE: "WS-9", SESSION: "b1"})
    rows.append({E: "EMP-bad", PEER: "PG-teller", VERB: "login",
                 TS: "2026-01-15T02:30:00Z", OFFH: True, GEO: "London", DEVICE: "WS-9", SESSION: "b1"})
    # dormant reactivation (>30d gap) + escalation, off-hours
    rows.append({E: "EMP-bad", PEER: "PG-teller", VERB: "grant_entitlement",
                 TS: "2026-03-20T03:00:00Z", OFFH: True, GEO: "London", DEVICE: "WS-9", SESSION: "b2"})
    return pd.DataFrame(rows)
