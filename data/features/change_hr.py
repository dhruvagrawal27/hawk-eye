"""Change / HR feature family (DATA-21; blueprint Part 6.4 + Part 12 slow-lane signals).

Every 6.4 feature plus slow-lane additions over a flattened-L0 DataFrame:

  * entitlement self-grant + short-lived grants timed around transactions
  * role-change recency / tenure / leaver-notice-period window
  * referrer-cluster signal
  * toxic-combination flags (conflicting entitlements / acted on a self-granted right)
  * SLOW: appraiser-is-borrower
  * SLOW: disbursement-to-non-sanctioned-account
  * SLOW: no-tax-footprint (ghost employee)

Status: REAL (numpy/pandas only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

E = "actor.employee_id"
ROLE = "actor.role"
TENURE = "actor.tenure_days"
LEAVER = "actor.leaver_flag"
NOTICE = "actor.notice_period"
MGR = "actor.manager_id"
VERB = "action.verb"
TS = "context.ts"
ENT = "object.entitlement_id"
ACCT = "object.account_id"
TARGET = "linkage.customer_account"  # the subject the actor acts on (borrower/sanctioned acct)
GRANTEE = "linkage.maker_id"          # who received the grant (for self-grant detection)

# entitlement pairs that together are a Segregation-of-Duties violation
TOXIC_PAIRS = {
    frozenset({"create_payment", "approve_payment"}),
    frozenset({"create_vendor", "approve_invoice"}),
    frozenset({"post_journal", "reconcile"}),
    frozenset({"disburse_loan", "appraise_loan"}),
}


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[TS], utc=True, errors="coerce")


def entitlement_self_grant(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of grant events where the actor granted an entitlement to
    themselves (grantee == actor)."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["grant_entitlement", "self_grant"])].copy()
    if d.empty:
        return pd.Series(dtype=int)
    if GRANTEE in d.columns:
        self_mask = d[GRANTEE].isna() | (d[GRANTEE].astype(str) == d[E].astype(str))
    else:
        self_mask = pd.Series(True, index=d.index)
    return d[self_mask].groupby(E).size().rename("entitlement_self_grant")


def short_lived_grant_around_txn(df: pd.DataFrame, window_hours: int = 24) -> pd.Series:
    """Per-entity flag: a grant followed by a revoke within `window_hours`, with a
    value-bearing transaction by the same actor in between (the privilege self-grant
    timed around a fraudulent approval typology)."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df.copy()
    d["_t"] = _ts(d)
    out = {}
    for ent, grp in d.groupby(E):
        g = grp.sort_values("_t")
        grants = g[g[VERB].isin(["grant_entitlement", "self_grant"])]
        revokes = g[g[VERB] == "revoke_entitlement"]
        txns = g[g[VERB].isin(["approve_payment", "post_payment", "disburse_loan"])]
        flag = False
        for _, gr in grants.iterrows():
            rv = revokes[revokes["_t"] > gr["_t"]]
            if rv.empty:
                continue
            rv_t = rv["_t"].iloc[0]
            if (rv_t - gr["_t"]) <= pd.Timedelta(hours=window_hours):
                between = txns[(txns["_t"] >= gr["_t"]) & (txns["_t"] <= rv_t)]
                if not between.empty:
                    flag = True
                    break
        out[str(ent)] = flag
    return pd.Series(out, name="short_lived_grant_around_txn")


def role_change_recency(df: pd.DataFrame) -> pd.DataFrame:
    """Per-entity: days since last role_change, tenure_days, and a
    `leaver_notice_window` flag (leaver or notice-period actor — the high-risk
    bulk-exfiltration window)."""
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["_t"] = _ts(d)
    ref = d["_t"].max()
    out = {}
    for ent, grp in d.groupby(E):
        rc = grp[grp[VERB] == "role_change"]["_t"]
        recency = (ref - rc.max()).total_seconds() / 86400.0 if len(rc) else np.nan
        tenure = pd.to_numeric(grp.get(TENURE), errors="coerce").dropna()
        leaver = bool(grp.get(LEAVER, pd.Series(False)).fillna(False).astype(bool).any())
        notice = bool(grp.get(NOTICE, pd.Series(False)).fillna(False).astype(bool).any())
        out[str(ent)] = {
            "role_change_recency_days": recency,
            "tenure_days": float(tenure.iloc[0]) if len(tenure) else np.nan,
            "leaver_notice_window": leaver or notice,
        }
    return pd.DataFrame(out).T


def referrer_cluster(df: pd.DataFrame, min_cluster: int = 3) -> pd.Series:
    """Per-manager count of reports — a manager who referred/onboarded an unusually large
    cluster (>= min_cluster) is flagged (collusive hiring / referral ring)."""
    if df.empty or MGR not in df.columns:
        return pd.Series(dtype=int)
    reports = df.dropna(subset=[MGR]).groupby(MGR)[E].nunique()
    flagged = reports[reports >= min_cluster]
    return flagged.rename("referrer_cluster")


def toxic_combination(df: pd.DataFrame) -> pd.Series:
    """Per-entity flag: the actor performed BOTH verbs of a toxic (SoD-violating) pair,
    OR acted on a right they self-granted."""
    if df.empty:
        return pd.Series(dtype=bool)
    verbs_by_ent = df.groupby(E)[VERB].apply(lambda s: set(s))
    out = {}
    for ent, verbs in verbs_by_ent.items():
        out[str(ent)] = any(pair <= verbs for pair in TOXIC_PAIRS)
    # acted on self-granted right: self-grant + a value-bearing action
    sg = df[df[VERB].isin(["grant_entitlement", "self_grant"])].groupby(E).size()
    acted = df[df[VERB].isin(["approve_payment", "disburse_loan"])].groupby(E).size()
    for ent in sg.index:
        if ent in acted.index:
            out[str(ent)] = True
    return pd.Series(out, name="toxic_combination")


def appraiser_is_borrower(df: pd.DataFrame) -> pd.Series:
    """SLOW: per-entity flag where the actor appraised a loan whose borrower account is
    their own (linkage.customer_account points back to the appraiser's account / id)."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df[df[VERB].isin(["appraise_loan", "value_collateral"])].copy()
    if d.empty:
        return pd.Series(dtype=bool)
    out = {}
    for ent, grp in d.groupby(E):
        tgt = grp.get(TARGET)
        flag = False
        if tgt is not None:
            flag = bool((tgt.astype(str) == str(ent)).any() or
                        tgt.astype(str).str.contains(str(ent), na=False).any())
        out[str(ent)] = flag
    return pd.Series(out, name="appraiser_is_borrower")


def disbursement_to_non_sanctioned(df: pd.DataFrame) -> pd.Series:
    """SLOW: per-entity count of loan disbursements whose destination account differs
    from the sanctioned account. The simulator stamps the sanctioned account in
    `object.account_id` and the actual destination in `linkage.customer_account`."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB] == "disburse_loan"].copy()
    if d.empty or ACCT not in d.columns or TARGET not in d.columns:
        return pd.Series(dtype=int)
    mismatch = d[ACCT].notna() & d[TARGET].notna() & (d[ACCT].astype(str) != d[TARGET].astype(str))
    return d[mismatch].groupby(E).size().rename("disbursement_to_non_sanctioned")


def no_tax_footprint(df: pd.DataFrame) -> pd.Series:
    """SLOW: per-payee flag (ghost employee) — an actor that RECEIVES payroll
    (`payroll_credit`) but has NO `tax_deduction`/`tds` event ever. Keyed by the payee
    in linkage.customer_account."""
    if df.empty:
        return pd.Series(dtype=bool)
    key = TARGET if TARGET in df.columns else E
    payees = set(df.loc[df[VERB] == "payroll_credit", key].dropna().astype(str))
    taxed = set(df.loc[df[VERB].isin(["tax_deduction", "tds"]), key].dropna().astype(str))
    out = {p: (p not in taxed) for p in payees}
    return pd.Series(out, name="no_tax_footprint")


def demo_frame() -> pd.DataFrame:
    """Frame with a self-granting actor, a ghost employee, and a self-appraising borrower."""
    rows = []
    base = pd.Timestamp("2026-01-01T03:00:00Z")
    # self-grant then approve then revoke within a day + toxic combination
    rows.append({E: "EMP-bad", ROLE: "ops", VERB: "self_grant", TS: "2026-01-01T03:00:00Z",
                 ENT: "approve_payment", GRANTEE: "EMP-bad"})
    rows.append({E: "EMP-bad", ROLE: "ops", VERB: "approve_payment", TS: "2026-01-01T03:30:00Z",
                 ACCT: "ACCT-1"})
    rows.append({E: "EMP-bad", ROLE: "ops", VERB: "revoke_entitlement", TS: "2026-01-01T05:00:00Z",
                 ENT: "approve_payment"})
    rows.append({E: "EMP-bad", ROLE: "ops", VERB: "create_payment", TS: "2026-01-01T03:20:00Z"})
    # ghost employee: payroll credit but no tax footprint
    rows.append({E: "EMP-hr", ROLE: "hr", VERB: "payroll_credit", TS: "2026-01-31T10:00:00Z",
                 TARGET: "EMP-ghost"})
    # legit employee with tax
    rows.append({E: "EMP-hr", ROLE: "hr", VERB: "payroll_credit", TS: "2026-01-31T10:00:00Z",
                 TARGET: "EMP-real"})
    rows.append({E: "EMP-hr", ROLE: "hr", VERB: "tax_deduction", TS: "2026-01-31T10:05:00Z",
                 TARGET: "EMP-real"})
    # self-appraising borrower + disbursement to non-sanctioned account
    rows.append({E: "EMP-loan", ROLE: "credit", VERB: "appraise_loan", TS: "2026-02-01T10:00:00Z",
                 TARGET: "EMP-loan"})
    rows.append({E: "EMP-loan", ROLE: "credit", VERB: "disburse_loan", TS: "2026-02-01T11:00:00Z",
                 ACCT: "ACCT-sanctioned", TARGET: "ACCT-other"})
    return pd.DataFrame(rows)
