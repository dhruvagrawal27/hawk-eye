"""Mock TEE confidential-compute attestation (PLATFORM-14, blueprint Part 25.2/25.4).

MOCK: there is no real confidential-compute hardware here. This simulates the NEAR AI
gateway's per-request **dual attestation** (Intel TDX CPU + NVIDIA H200 GPU), signed
with a LOCAL Ed25519 key, plus a verifier. It also enforces the **tokenize-before-egress**
policy (Part 25.3): a prompt that still contains raw PII is rejected — no quote is issued.

Real swap (Part 26.4): the on-prem H100/H200-in-TDX node running gpt-oss-120b emits real
TDX + NVIDIA quotes; this verifier is replaced by the genuine attestation verification
service. The audit-memo fields (provider, tee_attested, attestation_id, model, prompt_hash,
ts) match BACKEND.md §7 exactly so nothing downstream changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature

# --- local mock signing key (regenerated per process; prod = real TEE quotes) ---
_SIGNING_KEY = Ed25519PrivateKey.generate()
_PUBLIC_KEY: Ed25519PublicKey = _SIGNING_KEY.public_key()

# Raw-PII heuristics: if any of these match the (supposedly tokenized) prompt, the
# tokenize-before-egress policy was violated -> refuse attestation (Part 25.3).
_PII_PATTERNS = [
    re.compile(r"\b\d{16}\b"),  # 16-digit PAN/card
    re.compile(r"\b\d{9,18}\b"),  # bank account numbers
    re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # Indian PAN (income-tax)
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email
    re.compile(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b"),  # Indian mobile
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),  # Aadhaar-like
]


def public_key_hex() -> str:
    from cryptography.hazmat.primitives import serialization

    return _PUBLIC_KEY.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def pii_leak(prompt: str) -> str | None:
    """Return the name of the first raw-PII pattern found, or None if clean."""
    for pat in _PII_PATTERNS:
        if pat.search(prompt or ""):
            return pat.pattern
    return None


def _measurement(component: str, nonce: str, model: str) -> str:
    """Deterministic mock measurement (MRTD/MRSEAM-like) for a component."""
    return hashlib.sha384(f"{component}|{model}|{nonce}".encode()).hexdigest()


def _canonical(report: dict) -> bytes:
    """Stable bytes over the signed fields (excludes the signature itself)."""
    signed = {
        k: report[k]
        for k in (
            "provider",
            "model",
            "prompt_hash",
            "ts",
            "enclave_mode",
            "cpu_quote",
            "gpu_quote",
        )
    }
    return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()


def issue_quote(
    prompt: str, model: str, provider: str, enclave_mode: bool, nonce: str | None = None
) -> dict:
    """Issue a signed dual (TDX + H200) attestation quote for one request.

    Raises ValueError if the prompt still contains raw PII (tokenize-before-egress).
    """
    leak = pii_leak(prompt)
    if leak:
        raise ValueError(
            f"PII not tokenized before egress (matched /{leak}/); refusing attestation"
        )

    nonce = (
        nonce or hashlib.sha256(f"{prompt}{time.time_ns()}".encode()).hexdigest()[:16]
    )
    prompt_hash = hashlib.sha256((prompt or "").encode()).hexdigest()[:16]
    report_data = hashlib.sha256(f"{prompt_hash}|{nonce}".encode()).hexdigest()

    cpu_quote = {
        "tee": "intel-tdx",
        "type": "TDX_QUOTE",
        "fmspc": "00606A000000",
        "mrtd": _measurement("intel-tdx", nonce, model),
        "report_data": report_data,
        "nonce": nonce,
        "tcb_status": "UpToDate",
    }
    gpu_quote = {
        "tee": "nvidia-h200",
        "type": "NV_GPU_ATTESTATION",
        "arch": "Hopper",
        "measurement": _measurement("nvidia-h200", nonce, model),
        "report_data": report_data,
        "nonce": nonce,
        "driver_attested": True,
    }
    report = {
        "provider": provider,
        "model": model,
        "prompt_hash": prompt_hash,
        "ts": time.time(),
        "enclave_mode": enclave_mode,  # True => "TLS terminates inside the enclave" (Part 25.2)
        "cpu_quote": cpu_quote,
        "gpu_quote": gpu_quote,
    }
    sig = _SIGNING_KEY.sign(_canonical(report)).hex()
    att_id = "att_" + hashlib.sha256(sig.encode()).hexdigest()[:6]
    report.update(
        {
            "attestation_id": att_id,
            "signature": sig,
            "tee_attested": True,  # audit-memo (BACKEND.md §7)
            "pii_tokenized": True,
            "mock": True,  # honesty: this is a simulated quote
        }
    )
    return report


def verify_quote(report: dict) -> dict:
    """Verify a dual quote. Returns {valid, reasons, attestation_id}."""
    reasons: list[str] = []
    sig = report.get("signature")
    if not sig:
        return {
            "valid": False,
            "reasons": ["missing signature"],
            "attestation_id": report.get("attestation_id"),
        }
    try:
        _PUBLIC_KEY.verify(bytes.fromhex(sig), _canonical(report))
    except (InvalidSignature, ValueError, KeyError):
        reasons.append("signature invalid or payload tampered")

    cpu, gpu = report.get("cpu_quote", {}), report.get("gpu_quote", {})
    if cpu.get("tee") != "intel-tdx" or not cpu.get("mrtd"):
        reasons.append("CPU (TDX) quote missing/invalid")
    if gpu.get("tee") != "nvidia-h200" or not gpu.get("measurement"):
        reasons.append("GPU (H200) quote missing/invalid")
    if cpu.get("report_data") != gpu.get("report_data"):
        reasons.append("CPU/GPU report_data mismatch (not a single bound request)")
    if not report.get("enclave_mode"):
        reasons.append("enclave_mode false (TLS not terminated inside enclave)")

    return {
        "valid": not reasons,
        "reasons": reasons or ["ok"],
        "attestation_id": report.get("attestation_id"),
    }
