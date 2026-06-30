"""Transaction feature family (DATA-20; blueprint Part 6.2 + Part 12 slow-lane signals).

Every 6.2 feature plus the slow-lane additions, each a pure function over a flattened
L0 DataFrame returning a per-entity (or per-operator) Series:

  * amount z-score (personal & peer)
  * just-under-threshold clustering (structuring)
  * round-number bias
  * velocity / burst in sliding windows
  * new-beneficiary -> high-value latency
  * maker-checker pairing frequency
  * reversal clustering per operator
  * fee / rate-override frequency
  * suspense / nostro aging + same-person post-and-reconcile
  * SWIFT <-> CBS reconciliation mismatch (reads linkage.swift_ref / linkage.cbs_ref)
  * standing-instruction / beneficiary-modification events
  * P&L-vs-mark / mismarking divergence (rogue-trader slow signal)
  * per-analyst alert-clear-rate disproportion + reopened-then-cleared (AML suppression)

Status: REAL (numpy/pandas only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.config import feature_key
from data.features.baselines import compute_baselines

E = "actor.employee_id"
PEER = "actor.peer_group"
VERB = "action.verb"
TS = "context.ts"
AMOUNT = "object.amount"
BENE = "object.beneficiary_id"
ACCT = "object.account_id"
MC = "action.maker_checker"
SWIFT = "linkage.swift_ref"
CBS = "linkage.cbs_ref"
MAKER = "linkage.maker_id"
CHECKER = "linkage.checker_id"


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[TS], utc=True, errors="coerce")


def amount_zscore(df: pd.DataFrame, scope: str = "personal", window: str = "all") -> pd.Series:
    """Per-event amount z-score against the entity's own ('personal') or peer baseline.

    Returns a Series aligned to df.index (per-event). Uses the time-decayed baselines.
    """
    if df.empty or AMOUNT not in df.columns:
        return pd.Series(dtype=float)
    bl = compute_baselines(df, "amount", AMOUNT, window=window)
    amt = pd.to_numeric(df[AMOUNT], errors="coerce")
    out = []
    for idx, ent in df[E].items():
        v = amt.loc[idx]
        if np.isnan(v):
            out.append(0.0)
            continue
        if scope == "peer":
            peer = bl._entity_peer.get(str(ent))
            stat = bl.per_peer.get(peer, bl.glob) if peer else bl.glob
        else:
            stat = bl.get(str(ent))
        out.append(stat.zscore(float(v)))
    return pd.Series(out, index=df.index, name=feature_key("<entity>", f"amount_z_{scope}", window))


def just_under_threshold(df: pd.DataFrame, threshold: int = 1000000, band: float = 0.1) -> pd.Series:
    """Per-entity count of amounts in [threshold*(1-band), threshold) — structuring just
    under a reporting limit (default INR 10,00,000 minor-unit-agnostic)."""
    if df.empty or AMOUNT not in df.columns:
        return pd.Series(dtype=int)
    amt = pd.to_numeric(df[AMOUNT], errors="coerce")
    lo = threshold * (1 - band)
    mask = (amt >= lo) & (amt < threshold)
    return df[mask].groupby(E).size().reindex(df[E].unique(), fill_value=0).rename("just_under_threshold")


def round_number_bias(df: pd.DataFrame, modulo: int = 100000) -> pd.Series:
    """Per-entity fraction of amounts that are exact round numbers (amount % modulo == 0)."""
    if df.empty or AMOUNT not in df.columns:
        return pd.Series(dtype=float)
    amt = pd.to_numeric(df[AMOUNT], errors="coerce").dropna()
    d = df.loc[amt.index].copy()
    d["_round"] = (amt % modulo == 0).astype(float)
    return d.groupby(E)["_round"].mean().rename("round_number_bias")


def velocity_burst(df: pd.DataFrame, window_minutes: int = 60) -> pd.Series:
    """Max count of value-bearing transactions in any rolling window per entity."""
    if df.empty:
        return pd.Series(dtype=float)
    d = df[pd.to_numeric(df.get(AMOUNT), errors="coerce").notna()].copy() if AMOUNT in df.columns else df.copy()
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
        out[str(ent)] = float(s.rolling(f"{window_minutes}min").sum().max())
    return pd.Series(out, name=f"velocity_burst_{window_minutes}m")


def new_beneficiary_high_value_latency(df: pd.DataFrame, high_value: int = 1000000) -> pd.DataFrame:
    """For each (maker) entity, the minimum minutes between a `create_beneficiary` and a
    subsequent high-value `approve_payment`/`post_payment` to that beneficiary. Short
    latency == the PNB beneficiary-then-approve typology. Returns per-entity min latency
    (minutes) and a flag."""
    if df.empty or BENE not in df.columns:
        return pd.DataFrame()
    d = df.copy()
    d["_t"] = _ts(d)
    d["_amt"] = pd.to_numeric(d.get(AMOUNT), errors="coerce")
    creates = d[d[VERB] == "create_beneficiary"][[E, BENE, "_t"]].dropna(subset=[BENE])
    pays = d[d[VERB].isin(["approve_payment", "post_payment"]) & (d["_amt"] >= high_value)]
    out = {}
    for ent, cgrp in creates.groupby(E):
        bene_create = cgrp.groupby(BENE)["_t"].min()
        p = pays[pays[E] == ent]
        best = np.inf
        for _, pr in p.iterrows():
            ct = bene_create.get(pr[BENE])
            if ct is not None and pd.notna(ct) and pr["_t"] >= ct:
                mins = (pr["_t"] - ct).total_seconds() / 60.0
                best = min(best, mins)
        if np.isfinite(best):
            out[str(ent)] = best
    res = pd.DataFrame({"min_latency_min": pd.Series(out)})
    res["new_bene_high_value_flag"] = res["min_latency_min"] < 1440  # within a day
    return res


def maker_checker_pairing(df: pd.DataFrame) -> pd.Series:
    """Per (maker,checker) ordered pair, the number of times they paired on approvals.
    A pair that recurs far more than others is a collusion candidate."""
    if df.empty or MAKER not in df.columns or CHECKER not in df.columns:
        return pd.Series(dtype=int)
    d = df.dropna(subset=[MAKER, CHECKER])
    if d.empty:
        return pd.Series(dtype=int)
    counts = d.groupby([MAKER, CHECKER]).size()
    counts.index = [f"{m}->{c}" for m, c in counts.index]
    return counts.rename("maker_checker_pairing")


def reversal_clustering(df: pd.DataFrame) -> pd.Series:
    """Per-operator count of reversal/void transactions — clustering signals abuse."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["reversal", "void", "reverse_txn"])]
    return d.groupby(E).size().rename("reversal_clustering")


def fee_override_frequency(df: pd.DataFrame) -> pd.Series:
    """Per-operator count of fee / rate / charge override events."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["fee_override", "rate_override", "charge_override", "waiver"])]
    return d.groupby(E).size().rename("fee_override_frequency")


def suspense_nostro_aging(df: pd.DataFrame, aging_days: int = 7) -> pd.DataFrame:
    """For suspense/nostro postings, per-entity: max aging (days an item stayed open
    before reconcile) and a `same_person_post_and_reconcile` flag (the lapping typology).

    Uses verbs `suspense_post`/`nostro_post` paired with `reconcile` on the same
    object.account_id."""
    if df.empty or ACCT not in df.columns:
        return pd.DataFrame()
    d = df.copy()
    d["_t"] = _ts(d)
    posts = d[d[VERB].isin(["suspense_post", "nostro_post"])]
    recs = d[d[VERB] == "reconcile"]
    rows = {}
    for acct, pgrp in posts.groupby(ACCT):
        post_row = pgrp.sort_values("_t").iloc[0]
        r = recs[recs[ACCT] == acct].sort_values("_t")
        if r.empty:
            aging = np.nan
            same = False
        else:
            rec_row = r.iloc[-1]
            aging = (rec_row["_t"] - post_row["_t"]).total_seconds() / 86400.0
            same = bool(post_row[E] == rec_row[E])
        ent = str(post_row[E])
        prev = rows.get(ent, {"max_aging_days": -1.0, "same_person_post_and_reconcile": False})
        prev["max_aging_days"] = max(prev["max_aging_days"], aging if pd.notna(aging) else 0.0)
        prev["same_person_post_and_reconcile"] = prev["same_person_post_and_reconcile"] or same
        rows[ent] = prev
    res = pd.DataFrame(rows).T
    if not res.empty:
        res["aged_flag"] = res["max_aging_days"] >= aging_days
    return res


def swift_cbs_mismatch(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of SWIFT/instrument messages with NO matching CBS posting —
    the PNB SWIFT-without-CBS control (reads linkage.swift_ref / linkage.cbs_ref).

    A row with a swift_ref but a null/missing cbs_ref (and no other row carrying that
    swift_ref's cbs match) is a mismatch.
    """
    if df.empty or SWIFT not in df.columns:
        return pd.Series(dtype=int)
    d = df.copy()
    has_swift = d[SWIFT].notna()
    matched_refs = set(d.loc[d[CBS].notna(), SWIFT].dropna()) if CBS in d.columns else set()
    mismatch = has_swift & ~d[SWIFT].isin(matched_refs)
    # also a row that has swift but its own cbs is null counts if no sibling matched it
    if CBS in d.columns:
        own_null = d[CBS].isna()
        mismatch = has_swift & own_null & ~d[SWIFT].isin(matched_refs)
    return d[mismatch].groupby(E).size().rename("swift_cbs_mismatch")


def beneficiary_modification(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of standing-instruction / beneficiary-modification events."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["modify_beneficiary", "standing_instruction", "modify_si", "update_beneficiary"])]
    return d.groupby(E).size().rename("beneficiary_modification")


def pnl_mark_divergence(df: pd.DataFrame, reported_col: str = "object.amount",
                        independent_col: str = "linkage.customer_account") -> pd.Series:
    """P&L-vs-mark / mismarking divergence (rogue-trader slow signal).

    Reads a trader-reported mark (`reported_col`, default object.amount) and an
    independent/observed valuation that the simulator stamps into a numeric column
    (default tries `object.mark_independent`, falling back to `independent_col`).
    Returns per-entity max |reported - independent| / |independent|.
    """
    if df.empty:
        return pd.Series(dtype=float)
    d = df.copy()
    ind_col = "object.mark_independent" if "object.mark_independent" in d.columns else independent_col
    if ind_col not in d.columns or reported_col not in d.columns:
        return pd.Series(dtype=float)
    rep = pd.to_numeric(d[reported_col], errors="coerce")
    ind = pd.to_numeric(d[ind_col], errors="coerce")
    valid = rep.notna() & ind.notna() & (ind.abs() > 1e-9)
    d = d[valid].copy()
    if d.empty:
        return pd.Series(dtype=float)
    d["_div"] = (rep[valid] - ind[valid]).abs() / ind[valid].abs()
    return d.groupby(E)["_div"].max().rename("pnl_mark_divergence")


def analyst_clear_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Per-analyst alert-clear-rate disproportion + reopened-then-cleared count (the AML
    alert-suppression signal, Part 12). Uses verbs `clear_alert`, `reopen_alert`.

    Returns per-entity: share of all clears, and count of reopened-then-cleared cycles
    (proxied by the same analyst having both a reopen and a later clear on the alert
    identified by object.account_id == alert id)."""
    if df.empty:
        return pd.DataFrame()
    d = df.copy()
    d["_t"] = _ts(d)
    clears = d[d[VERB] == "clear_alert"]
    total = len(clears)
    share = (clears.groupby(E).size() / total) if total else pd.Series(dtype=float)
    # reopened-then-cleared per analyst (per alert id in object.account_id)
    reopened = {}
    if ACCT in d.columns:
        for ent, grp in d[d[VERB].isin(["clear_alert", "reopen_alert"])].groupby(E):
            cnt = 0
            for _, g2 in grp.groupby(ACCT):
                g2 = g2.sort_values("_t")
                seen_reopen = False
                for _, r in g2.iterrows():
                    if r[VERB] == "reopen_alert":
                        seen_reopen = True
                    elif r[VERB] == "clear_alert" and seen_reopen:
                        cnt += 1
                        seen_reopen = False
            reopened[str(ent)] = cnt
    res = pd.DataFrame({"clear_share": share})
    res["reopened_then_cleared"] = pd.Series(reopened)
    res = res.fillna(0.0)
    return res


def demo_frame() -> pd.DataFrame:
    """Frame mixing benign payments and a beneficiary-then-approve + structuring actor."""
    rows = []
    base = pd.Timestamp("2026-01-01T10:00:00Z")
    for i in range(15):
        rows.append({E: "EMP-good", PEER: "PG-ops", VERB: "post_payment",
                     TS: (base + pd.Timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     AMOUNT: 50000 + (i % 4) * 1000, BENE: "BEN-1", ACCT: "ACCT-1"})
    # bad actor: create beneficiary then immediately approve a huge payment
    rows.append({E: "EMP-bad", PEER: "PG-ops", VERB: "create_beneficiary",
                 TS: "2026-02-01T02:00:00Z", AMOUNT: None, BENE: "BEN-9", ACCT: "ACCT-9"})
    rows.append({E: "EMP-bad", PEER: "PG-ops", VERB: "approve_payment",
                 TS: "2026-02-01T02:05:00Z", AMOUNT: 4800000, BENE: "BEN-9", ACCT: "ACCT-9"})
    # structuring: several just-under 1,000,000
    for i in range(4):
        rows.append({E: "EMP-bad", PEER: "PG-ops", VERB: "post_payment",
                     TS: (base + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     AMOUNT: 950000, BENE: "BEN-9", ACCT: "ACCT-9"})
    return pd.DataFrame(rows)
