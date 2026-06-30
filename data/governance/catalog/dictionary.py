"""Data catalog + data dictionary for the L0 unified event model (DATA-26).

Blueprint Part 28.2 (l.1202): "every field in the unified event model documented, owned,
and classified." Status: REAL.

This dictionary documents EVERY L0 field (the five groups Actor/Action/Object/Context/
Linkage plus the two top-level fields) with: dotted path, group, owner, python type,
and a human description. ``classification.py`` consumes this to attach a sensitivity tag
to each field. The dictionary is the single source of truth for downstream masking,
access, retention and the entity-360 timeline labels.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Owners per field group (who is accountable for the definition/quality of the field).
_GROUP_OWNER = {
    "top": "DATA",
    "actor": "DATA (HR/IAM source)",
    "action": "DATA (CBS/payments/app source)",
    "object": "DATA (CBS/payments source)",
    "context": "DATA (collector/runtime)",
    "linkage": "DATA (recon/MDM)",
}


@dataclass(frozen=True)
class FieldEntry:
    """One documented field in the L0 model."""

    path: str          # dotted path, e.g. "actor.employee_id"
    group: str         # top | actor | action | object | context | linkage
    dtype: str         # python type name
    description: str
    owner: str = "DATA"


def field_entry(path: str, group: str, dtype: str, description: str) -> FieldEntry:
    return FieldEntry(path, group, dtype, description, owner=_GROUP_OWNER.get(group, "DATA"))


# ---- EVERY L0 field, documented --------------------------------------------
DATA_DICTIONARY: list[FieldEntry] = [
    # top-level
    field_entry("event_id", "top", "str", "Deterministic event id (evt_*); idempotency key."),
    field_entry("ts", "top", "str", "Event time, UTC ISO-8601 ending in 'Z'."),
    # actor
    field_entry("actor.employee_id", "actor", "str", "Acting employee identity (EMP-*); the insider entity key."),
    field_entry("actor.role", "actor", "str", "Job role (e.g. ops_maker, dba, teller)."),
    field_entry("actor.dept", "actor", "str", "Department / function."),
    field_entry("actor.branch", "actor", "str", "Branch / location code."),
    field_entry("actor.tenure_days", "actor", "int", "Days of service; drives tenure features."),
    field_entry("actor.manager_id", "actor", "str", "Reporting manager identity (EMP-*)."),
    field_entry("actor.peer_group", "actor", "str", "Peer-group id for peer-anchored baselines."),
    field_entry("actor.privileged_flag", "actor", "bool", "Whether the actor holds privileged access."),
    field_entry("actor.leaver_flag", "actor", "bool", "Whether the actor is a leaver (joiner-mover-leaver)."),
    field_entry("actor.notice_period", "actor", "bool", "Whether the actor is within notice period (exfil window)."),
    # action
    field_entry("action.verb", "action", "str", "What happened (login, create_beneficiary, approve_payment, db_select...)."),
    field_entry("action.channel", "action", "str", "Channel/source (cbs, swift, rtgs, neft, imps, upi, db, dlp, hr, iam, pam)."),
    field_entry("action.maker_checker", "action", "str", "maker | checker | None (segregation-of-duties role)."),
    # object
    field_entry("object.account_id", "object", "str", "Affected account (ACCT-*)."),
    field_entry("object.beneficiary_id", "object", "str", "Affected beneficiary/payee (BEN-*)."),
    field_entry("object.table", "object", "str", "Table/dataset for data-layer events."),
    field_entry("object.entitlement_id", "object", "str", "Entitlement/role-grant id for change events."),
    field_entry("object.instrument", "object", "str", "Payment/trade instrument (SWIFT/LC/LoU)."),
    field_entry("object.amount", "object", "int", "Transaction amount in integer minor units."),
    field_entry("object.currency", "object", "str", "ISO currency code (INR default)."),
    # context
    field_entry("context.ts", "context", "str", "Context timestamp (mirrors top-level ts)."),
    field_entry("context.src_ip", "context", "str", "Source IP address of the action."),
    field_entry("context.device", "context", "str", "Originating device / workstation id."),
    field_entry("context.geo", "context", "str", "Geo/location of the action."),
    field_entry("context.session_id", "context", "str", "Session correlation id (sess_*)."),
    field_entry("context.layer", "context", "str", "application | database (where the action occurred)."),
    field_entry("context.is_off_hours", "context", "bool", "Whether the event fell outside business hours."),
    field_entry("context.host", "context", "str", "Host/server name for data-layer events."),
    # linkage
    field_entry("linkage.swift_ref", "linkage", "str", "SWIFT/instrument message reference (recon key)."),
    field_entry("linkage.cbs_ref", "linkage", "str", "CBS posting reference (recon key)."),
    field_entry("linkage.app_txn_id", "linkage", "str", "Application transaction id (app-txn<->DB-write join)."),
    field_entry("linkage.db_write_id", "linkage", "str", "Database write id (app-txn<->DB-write join)."),
    field_entry("linkage.maker_id", "linkage", "str", "Maker identity for maker<->checker join."),
    field_entry("linkage.checker_id", "linkage", "str", "Checker identity for maker<->checker join."),
    field_entry("linkage.customer_account", "linkage", "str", "Customer account for employee<->customer-account join."),
]


def all_field_paths() -> list[str]:
    """Every documented L0 field path."""
    return [e.path for e in DATA_DICTIONARY]


def as_dataframe() -> pd.DataFrame:
    """The dictionary as a pandas DataFrame (catalog export)."""
    return pd.DataFrame(
        [
            {"path": e.path, "group": e.group, "dtype": e.dtype,
             "owner": e.owner, "description": e.description}
            for e in DATA_DICTIONARY
        ]
    )
