"""PII tokenization (BACKEND-17, blueprint Part 25.3 / 25.5).

Deterministic keyed tokens — ``tok(value) = HMAC-SHA256(secret_key, value)`` truncated to a
readable token with a type prefix (``EMP-7f3a``, ``ACCT-4d22``, ``BEN-9b1c``). Tokenization runs
**before any egress** (especially before the narrative LLM call): the model sees behaviour +
structure + tokens, never raw PII. The HMAC key is custodied by PLATFORM (Vault) and read from the
environment — never hardcoded. The token↔real mapping lives only in the local re-id vault.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.config import settings

# Field-type → token prefix (Part 25.3 examples).
PREFIXES: dict[str, str] = {
    "employee": "EMP",
    "account": "ACCT",
    "beneficiary": "BEN",
    "customer": "CUST",
    "pan": "PAN",
    "phone": "PHONE",
    "name": "NAME",
    "address": "ADDR",
    "card": "CARD",
}

# Token length after the prefix (hex chars). 4 matches the blueprint sample tokens (7f3a/4d22/9b1c).
_TOKEN_LEN = 4


def _hmac_hex(value: str) -> str:
    key = settings.pii_hmac_key.encode("utf-8")
    return hmac.new(key, str(value).encode("utf-8"), hashlib.sha256).hexdigest()


def tokenize(value: Any, field_type: str = "employee") -> str:
    """Deterministically tokenize one PII value to ``<PREFIX>-<hex>`` (e.g. ``EMP-7f3a``)."""
    prefix = PREFIXES.get(field_type, field_type.upper()[:4] or "TOK")
    return f"{prefix}-{_hmac_hex(value)[:_TOKEN_LEN]}"


def is_token(value: str) -> bool:
    """True if ``value`` already looks like one of our tokens (already tokenized upstream by DATA)."""
    if not isinstance(value, str) or "-" not in value:
        return False
    prefix, _, suffix = value.partition("-")
    return prefix in PREFIXES.values() and len(suffix) >= _TOKEN_LEN and _ishex(suffix[:_TOKEN_LEN])


def _ishex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


# PII field names that must be tokenized before egress (the "perimeter" rule).
SENSITIVE_FIELDS = {
    "name": "name",
    "full_name": "name",
    "account_number": "account",
    "account_id": "account",
    "beneficiary_name": "beneficiary",
    "beneficiary_id": "beneficiary",
    "pan": "pan",
    "phone": "phone",
    "address": "address",
    "card_number": "card",
    "customer_id": "customer",
    "employee_id": "employee",
}


def tokenize_payload(payload: dict, *, vault=None) -> dict:
    """Tokenize every sensitive field in a nested dict **before egress** (e.g. narrative context).

    Already-tokenized values pass through unchanged. If a ``vault`` is supplied, the token↔real
    mapping is recorded so an authorized unmask can reverse it later.
    """
    return _walk(payload, vault)


def _walk(node: Any, vault) -> Any:
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            ftype = SENSITIVE_FIELDS.get(k)
            if ftype and isinstance(v, (str, int)) and not is_token(str(v)):
                token = tokenize(v, ftype)
                if vault is not None:
                    vault.store(token, str(v), ftype)
                out[k] = token
            else:
                out[k] = _walk(v, vault)
        return out
    if isinstance(node, list):
        return [_walk(item, vault) for item in node]
    return node


def assert_no_raw_pii(payload: dict) -> None:
    """Guard used in the narrative egress path: raise if any sensitive field still holds raw PII."""
    leaks: list[str] = []

    def _check(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                ftype = SENSITIVE_FIELDS.get(k)
                if ftype and isinstance(v, str) and not is_token(v):
                    leaks.append(f"{path}{k}")
                _check(v, f"{path}{k}.")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _check(item, f"{path}{i}.")

    _check(payload)
    if leaks:
        raise ValueError(f"raw PII would leave the perimeter: {leaks}")
