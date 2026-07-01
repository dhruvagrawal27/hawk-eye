"""M2.1 — Continuous per-user insider-risk index (0–100).

A STANDING per-privileged-user score composed from signals that already exist in the platform —
HR posture, access posture, and recent behavioural anomaly — into one explainable 0–100 index with
sub-scores and top drivers. This is NOT a new detector: it aggregates existing feature functions
(`data.features.identity_access`, `data.features.change_hr`) plus recent alert counts, so a bank
gets a live "which privileged staffer is drifting" gauge per user.

Cadence: batch (daily/hourly) — call `compute_insider_risk_index(events, alerts_30d)` over the
trailing window and write the result to the feature store / entity store. ALERT-ONLY: this is a
*displayed, explained score* for a human — it never triggers an automated action, and the composition
weights are stubs pending labelled calibration (do not auto-action on the index).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from data.features import change_hr as ch
from data.features import identity_access as ia

E = "actor.employee_id"
LEAVER = "actor.leaver_flag"
NOTICE = "actor.notice_period"

# Composition weights (STUB — flagged for calibration on labelled ground truth; risk register M2.1).
DEFAULT_WEIGHTS = {"hr": 0.30, "access": 0.35, "anomaly": 0.35}

# Saturating caps per raw signal: value/cap clipped to [0,1] (monotone, robust on sparse data).
_CAPS = {
    "no_leave_taken_streak": 250.0,       # days worked without leave
    "entitlement_change_velocity": 5.0,   # grants in the window
    "standing_privilege_count": 5.0,
    "dormant_reactivation": 3.0,
    "recent_alert_count": 5.0,
}
# Recency ramps: a signal within N days ramps 1→0 as it ages out.
_GRIEVANCE_RAMP_DAYS = 180.0
_ROLE_CHANGE_RAMP_DAYS = 90.0


@dataclass
class RiskComponent:
    name: str
    group: str                # "hr" | "access" | "anomaly"
    value: float              # normalized [0,1]
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InsiderRiskIndex:
    employee_id: str
    composite: int            # 0–100
    hr_score: float           # 0–1
    access_score: float       # 0–1
    anomaly_score: float      # 0–1
    components: list[RiskComponent] = field(default_factory=list)
    top_drivers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["components"] = [c.to_dict() if isinstance(c, RiskComponent) else c for c in self.components]
        return d


def _sat(x: float, cap: float) -> float:
    if x is None or cap <= 0:
        return 0.0
    return max(0.0, min(1.0, float(x) / cap))


def _recency_ramp(days: float, ramp: float) -> float:
    """Recent event → ~1.0, ramping to 0 by `ramp` days; NaN/absent → 0.0 (no signal)."""
    if days is None or pd.isna(days):
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(days) / ramp))


def _mean(vals: list[float]) -> float:
    vals = [v for v in vals if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else 0.0


def compute_insider_risk_index(
    events: pd.DataFrame,
    alerts_30d: dict[str, int] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, InsiderRiskIndex]:
    """Per-employee insider-risk index over the trailing-window `events` (flattened L0).

    `alerts_30d` maps employee_id → count of alerts in the last 30d (recent-anomaly signal).
    Returns {employee_id: InsiderRiskIndex}. Empty input → {}.
    """
    if events is None or events.empty or E not in events.columns:
        return {}
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    alerts_30d = alerts_30d or {}

    # --- compute the underlying feature series once (each indexed by employee_id) ---
    no_leave = ia.no_leave_taken_streak(events)
    ent_vel = ia.entitlement_change_velocity(events)
    dormant = ia.dormant_reactivation(events)
    offh = ia.offhours_score(events)
    standing = ia.standing_privilege(events)
    griev_rec = ch.grievance_recency(events)
    role_rec = ch.role_change_recency(events)  # DataFrame w/ role_change_recency_days, leaver_notice_window

    def _get(series: pd.Series, emp: str, default=0.0):
        try:
            v = series.get(emp, default)
            return default if pd.isna(v) else v
        except Exception:
            return default

    # leaver/notice from actor flags (per-employee any-True)
    def _flag(col: str) -> set[str]:
        if col not in events.columns:
            return set()
        s = events[[E, col]].copy()
        s[col] = s[col].fillna(False).astype(bool)
        return set(s[s[col]][E].astype(str))

    leavers = _flag(LEAVER) | _flag(NOTICE)

    employees = sorted(events[E].dropna().astype(str).unique())
    out: dict[str, InsiderRiskIndex] = {}
    for emp in employees:
        comps: list[RiskComponent] = []

        # HR posture
        c_leave = _sat(_get(no_leave, emp), _CAPS["no_leave_taken_streak"])
        c_griev = _recency_ramp(_get(griev_rec, emp, None), _GRIEVANCE_RAMP_DAYS)
        role_days = role_rec.loc[emp, "role_change_recency_days"] if (
            not role_rec.empty and emp in role_rec.index
        ) else None
        c_role = _recency_ramp(role_days, _ROLE_CHANGE_RAMP_DAYS)
        c_leaver = 1.0 if emp in leavers else 0.0
        comps += [
            RiskComponent("no_leave_taken_streak", "hr", c_leave, "days worked without leave"),
            RiskComponent("grievance_recency", "hr", c_griev, "recent grievance filed"),
            RiskComponent("role_change_recency", "hr", c_role, "recent role change"),
            RiskComponent("leaver_or_notice", "hr", c_leaver, "leaver / notice-period window"),
        ]
        hr = _mean([c_leave, c_griev, c_role, c_leaver])

        # Access posture
        c_ent = _sat(_get(ent_vel, emp), _CAPS["entitlement_change_velocity"])
        st = standing.loc[emp, "standing_privilege_count"] if (
            not standing.empty and emp in standing.index
        ) else 0.0
        c_standing = _sat(st, _CAPS["standing_privilege_count"])
        c_dormant = _sat(_get(dormant, emp), _CAPS["dormant_reactivation"])
        comps += [
            RiskComponent("entitlement_change_velocity", "access", c_ent, "entitlement-change velocity"),
            RiskComponent("standing_privilege", "access", c_standing, "unexercised held entitlements"),
            RiskComponent("dormant_reactivation", "access", c_dormant, "dormant account reactivation"),
        ]
        access = _mean([c_ent, c_standing, c_dormant])

        # Recent-anomaly posture
        c_offh = max(0.0, min(1.0, float(_get(offh, emp))))
        c_alerts = _sat(alerts_30d.get(emp, 0), _CAPS["recent_alert_count"])
        comps += [
            RiskComponent("offhours_score", "anomaly", c_offh, "off-hours activity"),
            RiskComponent("recent_alerts_30d", "anomaly", c_alerts, "alerts in the last 30 days"),
        ]
        anomaly = _mean([c_offh, c_alerts])

        composite = int(round((w["hr"] * hr + w["access"] * access + w["anomaly"] * anomaly) * 100))
        composite = max(0, min(100, composite))
        drivers = [c.name for c in sorted(comps, key=lambda c: c.value, reverse=True) if c.value > 0][:3]

        out[emp] = InsiderRiskIndex(
            employee_id=emp,
            composite=composite,
            hr_score=hr,
            access_score=access,
            anomaly_score=anomaly,
            components=comps,
            top_drivers=drivers,
        )
    return out
