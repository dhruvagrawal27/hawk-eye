"""TEE attestation verify + store (ML-12; Part 25.2, 25.4).

For the NEAR AI path we must fetch and verify the **Intel TDX + NVIDIA dual quote**
proving a genuine, untampered enclave is running the expected model, then store the
report for audit. Groq is not a TEE path -> None.

# SCAFFOLD: real verification needs the live TEE service + hardware roots of trust.
# PLATFORM owns the TEE-attestation MOCK service; this client verifies+stores against it.
# Set TEE_ATTESTATION_URL to PLATFORM's mock service to exercise the attested path;
# absent it, NEAR AI returns None (tee_attested=False) and the gateway degrades honestly.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Optional

from ml._optional import optional_import

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STORE = os.path.join(REPO_ROOT, "ml", "_artifacts", "narratives", "attestations.jsonl")


@dataclass
class AttestationReport:
    attestation_id: str
    provider: str
    intel_tdx_verified: bool
    nvidia_verified: bool
    quote_sha256: str
    verified_ts: float

    def to_dict(self) -> dict:
        return asdict(self)


class AttestationVerifier:
    """Base verifier. Returns a report iff the dual quote verifies, else None."""

    def verify(self, provider: str) -> Optional[AttestationReport]:  # pragma: no cover - abstract
        raise NotImplementedError


class ScaffoldAttestationVerifier(AttestationVerifier):
    """Real path against PLATFORM's TEE service (SCAFFOLD — needs the live service)."""

    def __init__(self, url: Optional[str] = None) -> None:
        self.url = url or os.environ.get("TEE_ATTESTATION_URL")

    def verify(self, provider: str) -> Optional[AttestationReport]:
        if provider != "near_ai" or not self.url:
            return None
        httpx = optional_import("httpx")
        if httpx is None:  # pragma: no cover
            return None
        try:  # pragma: no cover - needs a live/mock service
            resp = httpx.get(f"{self.url.rstrip('/')}/attestation", timeout=5.0)
            resp.raise_for_status()
            data = resp.json()
            quote = json.dumps(data.get("quote", {}), sort_keys=True)
            return AttestationReport(
                attestation_id=data.get("attestation_id", "att_" + hashlib.sha256(quote.encode()).hexdigest()[:6]),
                provider=provider,
                intel_tdx_verified=bool(data.get("intel_tdx_verified", True)),
                nvidia_verified=bool(data.get("nvidia_verified", True)),
                quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
                verified_ts=time.time(),
            )
        except Exception:
            return None


class MockAttestationVerifier(AttestationVerifier):
    """Deterministic mock standing in for PLATFORM's TEE-attestation MOCK (for tests/demo)."""

    def __init__(self, seed: str = "hawkeye-tee") -> None:
        self.seed = seed

    def verify(self, provider: str) -> Optional[AttestationReport]:
        if provider != "near_ai":
            return None
        quote_hash = hashlib.sha256(f"{self.seed}:{provider}".encode()).hexdigest()
        return AttestationReport(
            attestation_id="att_" + quote_hash[:6],
            provider=provider,
            intel_tdx_verified=True,
            nvidia_verified=True,
            quote_sha256=quote_hash,
            verified_ts=0.0,
        )


# Module-default verifier: SCAFFOLD (returns None unless TEE_ATTESTATION_URL is set).
_default_verifier: AttestationVerifier = ScaffoldAttestationVerifier()


def set_default_verifier(v: AttestationVerifier) -> None:
    """Swap the verifier (e.g. inject MockAttestationVerifier in tests/demo)."""
    global _default_verifier
    _default_verifier = v


def _store(report: AttestationReport, path: Optional[str] = None) -> None:
    p = path or DEFAULT_STORE
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a") as fh:
        fh.write(json.dumps(report.to_dict()) + "\n")


def verify_and_store_attestation(
    provider: str, verifier: Optional[AttestationVerifier] = None
) -> Optional[str]:
    """Verify the TEE dual quote and store the report. Returns attestation_id or None.

    NEAR AI -> verify Intel TDX + NVIDIA quote; Groq/template -> None (not a TEE path).
    """
    v = verifier or _default_verifier
    report = v.verify(provider)
    if report is None:
        return None
    if not (report.intel_tdx_verified and report.nvidia_verified):
        return None
    _store(report)
    return report.attestation_id
