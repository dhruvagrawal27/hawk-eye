"""Data classification: PII / PAN / sensitive vs operational (DATA-26).

Blueprint Part 28.2 (l.1203): "tag PII/PAN/sensitive vs operational; drives masking,
access, and retention." Seam 5.6: this classification DRIVES BACKEND's masking and the
re-identification policy; it is PUBLISHED for BACKEND/PLATFORM. Status: REAL.

Tags (most-restrictive first):
  - PAN        : primary account number / card-like identifiers (highest masking).
  - PII        : directly/indirectly identifies a person (employee/customer ids, IP,
                 device, geo) — masked for investigators per policy.
  - SENSITIVE  : security-relevant but not personal (session, entitlement, recon refs).
  - OPERATIONAL: non-personal operational metadata (verbs, flags, timestamps).

Every L0 field in the data dictionary gets exactly one tag, so BACKEND can mask the
right fields and PLATFORM can scope access. Synthetic-only: the *values* are tokenized
synthetic ids (EMP-/ACCT-/BEN-) so no real PII exists; the tags say which fields WOULD
be PII/PAN in production and therefore must be masked.
"""
from __future__ import annotations

from data.governance.catalog.dictionary import DATA_DICTIONARY, all_field_paths


class Tag:
    PAN = "PAN"
    PII = "PII"
    SENSITIVE = "sensitive"
    OPERATIONAL = "operational"


# Explicit per-field classification. Account/beneficiary/customer-account ids are
# PAN-class (account numbers); person/device/network identifiers are PII; security
# correlation refs are sensitive; everything else is operational.
_CLASSIFICATION: dict[str, str] = {
    # PAN — account-number-like
    "object.account_id": Tag.PAN,
    "object.beneficiary_id": Tag.PAN,
    "linkage.customer_account": Tag.PAN,
    # PII — identifies a person / their device / their network location
    "actor.employee_id": Tag.PII,
    "actor.manager_id": Tag.PII,
    "linkage.maker_id": Tag.PII,
    "linkage.checker_id": Tag.PII,
    "context.src_ip": Tag.PII,
    "context.device": Tag.PII,
    "context.geo": Tag.PII,
    "context.host": Tag.PII,
    # SENSITIVE — security-relevant correlation / authorization refs
    "context.session_id": Tag.SENSITIVE,
    "object.entitlement_id": Tag.SENSITIVE,
    "object.instrument": Tag.SENSITIVE,
    "linkage.swift_ref": Tag.SENSITIVE,
    "linkage.cbs_ref": Tag.SENSITIVE,
    "linkage.app_txn_id": Tag.SENSITIVE,
    "linkage.db_write_id": Tag.SENSITIVE,
    "object.table": Tag.SENSITIVE,
}


def classify(path: str) -> str:
    """Return the sensitivity tag for an L0 field path (default OPERATIONAL)."""
    return _CLASSIFICATION.get(path, Tag.OPERATIONAL)


def classification_map() -> dict[str, str]:
    """Full {field_path: tag} map over EVERY documented L0 field. Published for
    BACKEND/PLATFORM (seam 5.6)."""
    return {p: classify(p) for p in all_field_paths()}


def fields_with_tag(tag: str) -> list[str]:
    """All L0 field paths carrying ``tag``."""
    return [p for p, t in classification_map().items() if t == tag]


def fields_to_mask() -> list[str]:
    """Fields BACKEND must mask: everything PAN or PII (the maskable surface)."""
    cm = classification_map()
    return [p for p, t in cm.items() if t in (Tag.PAN, Tag.PII)]


def _demo() -> dict[str, str]:
    """Tiny demo helper for tests: the full classification map."""
    # Touch DATA_DICTIONARY so import-time coupling is explicit.
    assert len(DATA_DICTIONARY) > 0
    return classification_map()
