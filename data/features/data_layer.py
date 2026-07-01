"""Data-layer feature family (DATA-21; blueprint Part 6.3, l.235-240).

Every 6.3 feature over a flattened-L0 DataFrame:

  * export volume vs baseline + bulk-export flag + export-to-personal-channel
  * DB write/update with NO corresponding application transaction
    (uses linkage.app_txn_id / linkage.db_write_id)
  * sensitive-table / PII / PAN access outside role + unusual query shapes
  * logging / audit-config changes (log-tampering proxy)
  * shared / service / orphaned-account use + dormant-privileged activation

Status: REAL (numpy/pandas only).
"""
from __future__ import annotations

import pandas as pd

E = "actor.employee_id"
ROLE = "actor.role"
PRIV = "actor.privileged_flag"
PEER = "actor.peer_group"
VERB = "action.verb"
CHANNEL = "action.channel"
TS = "context.ts"
LAYER = "context.layer"
TABLE = "object.table"
APP_TXN = "linkage.app_txn_id"
DB_WRITE = "linkage.db_write_id"

SENSITIVE_TABLES = {"customer_pii", "card_pan", "accounts_master", "kyc", "salary"}
# personal/egress channels an export should NOT go to
PERSONAL_CHANNELS = {"personal_email", "usb", "gdrive", "dropbox", "webmail"}


def _ts(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df[TS], utc=True, errors="coerce")


def export_volume_vs_baseline(df: pd.DataFrame, bulk_rows: int = 10000) -> pd.DataFrame:
    """Per-entity export-row volume, z-score vs population, and a `bulk_export` flag.

    Export size is taken from `object.amount` on `export`/`download` verbs (rows/bytes)."""
    if df.empty:
        return pd.DataFrame()
    d = df[df[VERB].isin(["export", "download", "bulk_export"])].copy()
    if d.empty:
        return pd.DataFrame()
    d["_vol"] = pd.to_numeric(d.get("object.amount"), errors="coerce").fillna(1.0)
    vol = d.groupby(E)["_vol"].sum()
    mu, sd = vol.mean(), vol.std(ddof=0)
    z = (vol - mu) / sd if sd > 1e-9 else vol * 0.0
    res = pd.DataFrame({"export_volume": vol, "export_volume_z": z})
    res["bulk_export"] = vol >= bulk_rows
    return res


def export_to_personal_channel(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of exports/downloads sent to a personal/egress channel."""
    if df.empty or CHANNEL not in df.columns:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["export", "download", "bulk_export"]) & df[CHANNEL].isin(PERSONAL_CHANNELS)]
    return d.groupby(E).size().rename("export_to_personal_channel")


def db_write_without_app_txn(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of database writes with NO corresponding application transaction.

    A DB-layer write carries linkage.db_write_id; a legitimate one is correlated to an
    application transaction (linkage.app_txn_id present, and that app_txn_id exists in
    the application-layer events). A write with a null app_txn_id, or whose app_txn_id
    never appears at the application layer, is back-door data manipulation.
    """
    if df.empty:
        return pd.Series(dtype=int)
    d = df.copy()
    is_db_write = d[VERB].isin(["db_insert", "db_update", "db_delete", "db_write"])
    if LAYER in d.columns:
        is_db_write = is_db_write | ((d[LAYER] == "database") & d[VERB].astype(str).str.startswith("db_"))
    app_txn_ids = set(d.loc[d.get(LAYER) == "application", APP_TXN].dropna()) if APP_TXN in d.columns else set()
    if APP_TXN in d.columns:
        # also accept app_txn ids that appear anywhere at application layer
        app_txn_ids |= set(d[APP_TXN].dropna()) if LAYER not in d.columns else app_txn_ids
    writes = d[is_db_write]
    if writes.empty:
        return pd.Series(dtype=int)
    no_app = writes[APP_TXN].isna() if APP_TXN in writes.columns else pd.Series(True, index=writes.index)
    if APP_TXN in writes.columns:
        orphan = ~writes[APP_TXN].isin(app_txn_ids)
        flagged = writes[no_app | orphan]
    else:
        flagged = writes
    return flagged.groupby(E).size().rename("db_write_without_app_txn")


def sensitive_access_outside_role(df: pd.DataFrame, allowed_roles: set | None = None) -> pd.Series:
    """Per-entity count of accesses to sensitive/PII/PAN tables by an actor whose role is
    not authorised for them."""
    if df.empty or TABLE not in df.columns:
        return pd.Series(dtype=int)
    allowed = allowed_roles or {"dba", "kyc_officer", "compliance"}
    d = df[df[TABLE].isin(SENSITIVE_TABLES)].copy()
    if ROLE in d.columns:
        d = d[~d[ROLE].isin(allowed)]
    return d.groupby(E).size().rename("sensitive_access_outside_role")


def unusual_query_shape(df: pd.DataFrame, z_thresh: float = 3.0) -> pd.Series:
    """Per-entity flag for unusual query shapes: rows-scanned/returned (object.amount on
    db_select) that is a strong outlier vs the entity's own history (z > z_thresh)."""
    if df.empty:
        return pd.Series(dtype=bool)
    d = df[df[VERB].isin(["db_select", "query"])].copy()
    if d.empty:
        return pd.Series(dtype=bool)
    d["_rows"] = pd.to_numeric(d.get("object.amount"), errors="coerce").fillna(1.0)
    out = {}
    for ent, grp in d.groupby(E):
        v = grp["_rows"]
        mu, sd = v.mean(), v.std(ddof=0)
        out[str(ent)] = bool(sd > 1e-9 and ((v - mu) / sd).max() > z_thresh)
    return pd.Series(out, name="unusual_query_shape")


def log_tampering_proxy(df: pd.DataFrame) -> pd.Series:
    """Per-entity count of logging/audit-configuration changes (a log-tampering proxy)."""
    if df.empty:
        return pd.Series(dtype=int)
    d = df[df[VERB].isin(["audit_config_change", "disable_logging", "modify_audit", "clear_log"])]
    return d.groupby(E).size().rename("log_tampering_proxy")


def shared_or_orphaned_account(df: pd.DataFrame) -> pd.DataFrame:
    """Per-account-id flags: `shared` (used from >1 distinct device/host) and
    `service_or_orphaned` (a service/shared/orphaned account name pattern). Also a
    per-entity `dormant_privileged_activation` flag (privileged actor reactivating
    after a long gap)."""
    out = {}
    if not df.empty and "context.device" in df.columns:
        dev = df.groupby(E)["context.device"].nunique()
        out["n_devices"] = dev
    res = pd.DataFrame(out)
    if not res.empty:
        res["shared_account"] = res.get("n_devices", 0) > 1
    # service/orphaned heuristic by id pattern
    ents = pd.Series(df[E].unique()) if not df.empty else pd.Series([], dtype=str)
    svc = ents[ents.astype(str).str.contains("svc|shared|service|orphan", case=False, regex=True)]
    res = res.reindex(ents.astype(str), fill_value=0) if not res.empty else pd.DataFrame(index=ents.astype(str))
    res["service_or_orphaned"] = res.index.isin(svc.astype(str))
    # dormant privileged activation
    if PRIV in df.columns:
        d = df.copy()
        d["_t"] = _ts(d)
        flags = {}
        for ent, grp in d[d[PRIV].fillna(False).astype(bool)].groupby(E):
            t = grp["_t"].dropna().sort_values()
            flags[str(ent)] = bool(len(t) >= 2 and t.diff().max() >= pd.Timedelta(days=30))
        res["dormant_privileged_activation"] = pd.Series(flags).reindex(res.index).fillna(False)
    return res


def demo_frame() -> pd.DataFrame:
    """Frame mixing benign DB activity and a back-door + bulk-export actor."""
    rows = []
    base = pd.Timestamp("2026-01-01T11:00:00Z")
    # benign DBA: db writes correlated to app txns
    for i in range(5):
        rows.append({E: "EMP-dba", ROLE: "dba", PRIV: True, PEER: "PG-dba", VERB: "db_update",
                     TS: (base + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     LAYER: "database", TABLE: "accounts_master",
                     APP_TXN: f"txn{i}", DB_WRITE: f"w{i}", "context.device": "DBHOST"})
        rows.append({E: "EMP-app", ROLE: "ops", PRIV: False, PEER: "PG-ops", VERB: "post_payment",
                     TS: (base + pd.Timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     LAYER: "application", APP_TXN: f"txn{i}", "context.device": "WS-1"})
    # bad actor: db write with no app txn + bulk export to personal email + sensitive read
    rows.append({E: "EMP-bad", ROLE: "ops", PRIV: False, PEER: "PG-ops", VERB: "db_update",
                 TS: "2026-01-02T02:00:00Z", LAYER: "database", TABLE: "customer_pii",
                 APP_TXN: None, DB_WRITE: "w99", "context.device": "WS-9"})
    rows.append({E: "EMP-bad", ROLE: "ops", PRIV: False, PEER: "PG-ops", VERB: "bulk_export",
                 TS: "2026-01-02T02:10:00Z", CHANNEL: "personal_email", TABLE: "customer_pii",
                 "object.amount": 50000, "context.device": "WS-9"})
    return pd.DataFrame(rows)
