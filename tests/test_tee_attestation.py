"""Unit tests for the TEE-attestation mock (PLATFORM-14, Part 25.2/25.3/25.4)."""
import pytest
from teesvc import attestation


def test_attest_then_verify_roundtrip():
    rep = attestation.issue_quote("Alert EMP-7f3a paid BEN-9b1c off-hours",
                                  model="openai/gpt-oss-120b", provider="near_ai", enclave_mode=True)
    assert rep["tee_attested"] is True
    assert rep["attestation_id"].startswith("att_")
    assert rep["cpu_quote"]["tee"] == "intel-tdx"
    assert rep["gpu_quote"]["tee"] == "nvidia-h200"
    v = attestation.verify_quote(rep)
    assert v["valid"] is True, v["reasons"]


def test_tampered_quote_fails_verify():
    rep = attestation.issue_quote("tokenized prompt", model="m", provider="near_ai", enclave_mode=True)
    rep["model"] = "evil-model"   # tamper a signed field
    v = attestation.verify_quote(rep)
    assert v["valid"] is False
    assert any("tamper" in r or "invalid" in r for r in v["reasons"])


def test_enclave_mode_false_fails_verify():
    rep = attestation.issue_quote("p", model="m", provider="near_ai", enclave_mode=False)
    v = attestation.verify_quote(rep)
    assert v["valid"] is False
    assert any("enclave_mode false" in r for r in v["reasons"])


def test_cpu_gpu_bound_to_same_request():
    rep = attestation.issue_quote("p", model="m", provider="near_ai", enclave_mode=True)
    assert rep["cpu_quote"]["report_data"] == rep["gpu_quote"]["report_data"]


@pytest.mark.parametrize("leaky", [
    "card 4111111111111111 used",          # 16-digit PAN
    "PAN ABCDE1234F flagged",              # Indian PAN
    "contact john.doe@bank.com",           # email
    "mobile +91 9876543210",               # Indian mobile
    "account 123456789012",                # account number
])
def test_pii_leak_refused(leaky):
    """tokenize-before-egress (Part 25.3): raw PII must be refused."""
    assert attestation.pii_leak(leaky) is not None
    with pytest.raises(ValueError):
        attestation.issue_quote(leaky, model="m", provider="near_ai", enclave_mode=True)


def test_clean_tokenized_prompt_passes():
    assert attestation.pii_leak("EMP-7f3a paid BEN-9b1c ACCT-4d22") is None
