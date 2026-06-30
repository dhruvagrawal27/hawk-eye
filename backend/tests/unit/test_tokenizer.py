"""PII tokenization + vault + before-egress guard unit tests (BACKEND-17/18)."""

from __future__ import annotations

import re

import pytest

from app.pii import crypto
from app.pii.tokenizer import assert_no_raw_pii, is_token, tokenize, tokenize_payload
from app.pii.vault import ReidVault

_TOKEN_RE = re.compile(r"^[A-Z]+-[0-9a-f]{4}$")


def test_tokenize_is_deterministic_and_formatted():
    a = tokenize("Rakesh Kumar", "name")
    b = tokenize("Rakesh Kumar", "name")
    assert a == b  # deterministic (HMAC-SHA256 keyed)
    assert _TOKEN_RE.match(tokenize("123456789012", "account"))
    assert tokenize("x", "employee").startswith("EMP-")
    assert tokenize("y", "account").startswith("ACCT-")
    assert tokenize("z", "beneficiary").startswith("BEN-")


def test_is_token_detects_tokens():
    assert is_token(tokenize("acc", "account"))
    assert not is_token("Rakesh Kumar")


def test_vault_round_trip_encrypts_at_rest():
    vault = ReidVault()
    tok = tokenize("1234567890", "account")
    vault.store(tok, "1234567890", "account")
    # Stored ciphertext must NOT contain the plaintext.
    entry = vault._entries[tok]
    assert "1234567890" not in entry.ciphertext
    assert vault.resolve(tok) == "1234567890"


def test_tokenize_payload_before_egress_and_guard():
    payload = {"name": "Asha Nair", "account_number": "99887766", "risk": 87, "nested": {"pan": "ABCDE1234F"}}
    vault = ReidVault()
    out = tokenize_payload(payload, vault=vault)
    assert is_token(out["name"]) and is_token(out["account_number"]) and is_token(out["nested"]["pan"])
    assert out["risk"] == 87  # non-PII untouched
    assert_no_raw_pii(out)  # must not raise — nothing raw remains


def test_assert_no_raw_pii_raises_on_leak():
    with pytest.raises(ValueError):
        assert_no_raw_pii({"name": "Asha Nair"})  # raw name would leave the perimeter


def test_field_crypto_round_trip():
    blob = crypto.encrypt_field("ABCDE1234F")
    assert blob != "ABCDE1234F"
    assert crypto.decrypt_field(blob) == "ABCDE1234F"
    assert crypto.mask("99887766", keep=2) == "******66"
