"""Shared featurisation: flattened L0 events -> rectangular numeric matrices (ML-1).

Train and serve go through the SAME functions here, so a model fitted on the DATA
simulator output scores identically on synthetic fixtures (no train/serve skew).

* ``event_level_features``  -> per-event matrix (index = event_id) for L3 supervised.
* ``entity_level_features`` -> per-employee matrix (index = employee_id) for L2 UEBA.

All dtype checks use ``pd.api.types.*`` so this runs on pandas 2.3.x and 3.0.x.
Columns are the dotted flattened L0 names (``actor.employee_id``, ``object.amount``, ...).
Missing columns degrade gracefully to zeros/defaults so synthetic fixtures with a
subset of columns still produce a valid (zero-filled) matrix.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EMP = "actor.employee_id"
TS = "ts"
AMOUNT = "object.amount"
VERB = "action.verb"
CHANNEL = "action.channel"

# High-signal verbs we flag explicitly (one-hot-ish booleans).
RISK_VERBS = (
    "approve_payment",
    "create_beneficiary",
    "export",
    "grant_entitlement",
    "db_write",
    "login",
    "post_journal",
)


def _col(df: pd.DataFrame, name: str, default=0.0) -> pd.Series:
    """Return column ``name`` or a default-filled series of the right length/index."""
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index, name=name)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _bool_int(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    return _num(s).astype(int).clip(0, 1)


def _hour_dow(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    ts = pd.to_datetime(_col(df, TS, None), utc=True, errors="coerce")
    hour = ts.dt.hour.fillna(0).astype(int)
    dow = ts.dt.dayofweek.fillna(0).astype(int)
    return hour, dow


def event_level_features(events: pd.DataFrame) -> pd.DataFrame:
    """Per-event numeric features (index = event_id). Leakage-safe (no label, no future)."""
    df = events.copy()
    idx = _col(df, "event_id", None)
    hour, dow = _hour_dow(df)
    amount = _num(_col(df, AMOUNT)).astype(float)

    feat = pd.DataFrame(index=df.index)
    feat["amount"] = amount
    feat["log1p_amount"] = np.log1p(amount.clip(lower=0))
    feat["is_off_hours"] = _bool_int(_col(df, "context.is_off_hours", False))
    feat["tenure_days"] = _num(_col(df, "actor.tenure_days"))
    feat["privileged_flag"] = _bool_int(_col(df, "actor.privileged_flag", False))
    feat["leaver_flag"] = _bool_int(_col(df, "actor.leaver_flag", False))
    feat["notice_period"] = _bool_int(_col(df, "actor.notice_period", False))
    mc = _col(df, "action.maker_checker", "").astype(str)
    feat["is_maker"] = (mc == "maker").astype(int)
    feat["is_checker"] = (mc == "checker").astype(int)
    feat["hour"] = hour
    feat["dow"] = dow
    feat["is_weekend"] = (dow >= 5).astype(int)
    feat["has_beneficiary"] = (_col(df, "object.beneficiary_id", "").astype(str).str.len() > 0).astype(int)
    feat["has_account"] = (_col(df, "object.account_id", "").astype(str).str.len() > 0).astype(int)
    swift = _col(df, "linkage.swift_ref", "").astype(str).str.len() > 0
    cbs = _col(df, "linkage.cbs_ref", "").astype(str).str.len() > 0
    feat["has_swift_ref"] = swift.astype(int)
    feat["swift_without_cbs"] = (swift & ~cbs).astype(int)
    feat["db_write_no_app_txn"] = (
        (_col(df, "context.layer", "").astype(str) == "database")
        & (_col(df, "linkage.app_txn_id", "").astype(str).str.len() == 0)
    ).astype(int)

    verb = _col(df, VERB, "").astype(str)
    for v in RISK_VERBS:
        feat[f"verb_{v}"] = (verb == v).astype(int)

    # Per-entity contextual features (peer-relative amount z-score; rolling velocity).
    emp = _col(df, EMP, "__none__").astype(str)
    feat["amount_z_personal"] = _grouped_zscore(amount, emp)
    feat["new_beneficiary"] = _new_pair_flag(emp, _col(df, "object.beneficiary_id", "").astype(str))
    feat["velocity_1h"] = _rolling_count(df, emp, window="1h")

    feat.index = pd.Index(idx, name="event_id")
    return feat.fillna(0.0)


def entity_level_features(events: pd.DataFrame) -> pd.DataFrame:
    """Per-employee aggregate features (index = employee_id) for unsupervised UEBA."""
    df = events.copy()
    emp = _col(df, EMP, "__none__").astype(str)
    amount = _num(_col(df, AMOUNT)).astype(float)
    verb = _col(df, VERB, "").astype(str)
    offh = _bool_int(_col(df, "context.is_off_hours", False))

    g = pd.DataFrame({"emp": emp.values})
    g["amount"] = amount.values
    g["offh"] = offh.values
    g["verb"] = verb.values
    g["device"] = _col(df, "context.device", "").astype(str).values
    g["geo"] = _col(df, "context.geo", "").astype(str).values
    g["bene"] = _col(df, "object.beneficiary_id", "").astype(str).values
    g["priv"] = _bool_int(_col(df, "actor.privileged_flag", False)).values
    g["leaver"] = _bool_int(_col(df, "actor.leaver_flag", False)).values
    g["tenure"] = _num(_col(df, "actor.tenure_days")).values

    grp = g.groupby("emp", sort=True)
    out = pd.DataFrame(index=grp.size().index)
    out["n_events"] = grp.size()
    out["amount_mean"] = grp["amount"].mean()
    out["amount_std"] = grp["amount"].std().fillna(0.0)
    out["amount_max"] = grp["amount"].max()
    out["amount_sum"] = grp["amount"].sum()
    out["offhours_rate"] = grp["offh"].mean()
    out["n_distinct_verbs"] = grp["verb"].nunique()
    out["n_distinct_devices"] = grp["device"].apply(lambda s: s[s.str.len() > 0].nunique())
    out["n_distinct_geos"] = grp["geo"].apply(lambda s: s[s.str.len() > 0].nunique())
    out["n_distinct_bene"] = grp["bene"].apply(lambda s: s[s.str.len() > 0].nunique())
    out["privileged_flag"] = grp["priv"].max()
    out["leaver_flag"] = grp["leaver"].max()
    out["tenure_days"] = grp["tenure"].max()
    for v in ("approve_payment", "create_beneficiary", "export", "grant_entitlement", "db_write"):
        out[f"n_{v}"] = grp["verb"].apply(lambda s, vv=v: int((s == vv).sum()))
    out.index = pd.Index(out.index, name="employee_id")
    return out.fillna(0.0)


def join_event_labels(event_features: pd.DataFrame, labels: pd.DataFrame) -> pd.Series:
    """Return a 0/1 fraud label Series aligned to ``event_features.index`` (event_id)."""
    lab = labels.set_index("event_id")["is_fraud"] if "event_id" in labels.columns else labels["is_fraud"]
    y = lab.reindex(event_features.index).fillna(False)
    return _bool_int(y).rename("is_fraud")


def entity_labels(events: pd.DataFrame, labels: pd.DataFrame) -> pd.Series:
    """Per-employee label: 1 if the employee is ever a fraud actor (actor_id) on a fraud label."""
    emp_all = pd.Index(sorted(_col(events, EMP, "__none__").astype(str).unique()), name="employee_id")
    if "actor_id" in labels.columns and "is_fraud" in labels.columns:
        fraud = labels[_bool_int(labels["is_fraud"]) == 1]
        fraud_actors = set(fraud["actor_id"].dropna().astype(str).tolist())
    else:
        fraud_actors = set()
    return pd.Series([1 if e in fraud_actors else 0 for e in emp_all], index=emp_all, name="is_fraud_actor")


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _grouped_zscore(values: pd.Series, group: pd.Series) -> pd.Series:
    vals = values.reset_index(drop=True)
    grp = group.reset_index(drop=True)
    mean = vals.groupby(grp).transform("mean")
    std = vals.groupby(grp).transform("std").replace(0, np.nan).fillna(1.0)
    z = (vals - mean) / std
    z.index = values.index
    return z.fillna(0.0)


def _new_pair_flag(left: pd.Series, right: pd.Series) -> pd.Series:
    """1 the first time a (left,right) pair (employee,beneficiary) appears, else 0."""
    key = left.astype(str).reset_index(drop=True) + "|" + right.astype(str).reset_index(drop=True)
    valid = right.astype(str).reset_index(drop=True).str.len() > 0
    seen: set[str] = set()
    flags = []
    for k, v in zip(key, valid):
        if v and k not in seen:
            seen.add(k)
            flags.append(1)
        else:
            flags.append(0)
    out = pd.Series(flags, index=left.index)
    return out


def _rolling_count(df: pd.DataFrame, emp: pd.Series, window: str = "1h") -> pd.Series:
    ts = pd.to_datetime(_col(df, TS, None), utc=True, errors="coerce")
    tmp = pd.DataFrame({"emp": emp.values, "ts": ts.values, "one": 1}, index=df.index)
    tmp = tmp.dropna(subset=["ts"])
    if tmp.empty:
        return pd.Series(0, index=df.index)
    counts = pd.Series(0, index=df.index, dtype=float)
    for _, sub in tmp.groupby("emp", sort=False):
        sub = sub.sort_values("ts")
        rolled = sub.rolling(window, on="ts")["one"].sum()
        counts.loc[sub.index] = rolled.values
    return counts.fillna(1.0)
