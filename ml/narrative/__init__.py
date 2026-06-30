"""TEE-attested LLM narrative gateway (ML-10..13; blueprint Part 25).

narrate() failover: NEAR AI (TEE) -> Groq -> deterministic Jinja template. Every
narrative is grounded against reason codes, writes an audit memo, and is labelled
AI-generated/advisory. It EXPLAINS an alert — it never decides.
"""

from __future__ import annotations

from ml.narrative.attestation import (
    AttestationReport,
    MockAttestationVerifier,
    ScaffoldAttestationVerifier,
    set_default_verifier,
    verify_and_store_attestation,
)
from ml.narrative.audit_memo import AuditMemo, AuditMemoWriter, make_memo
from ml.narrative.gateway import SYSTEM_PROMPT, narrate, render_template
from ml.narrative.guardrails import RateLimiter, check_grounding, label_ai_generated
from ml.narrative.pii import tok

__all__ = [
    "narrate",
    "render_template",
    "SYSTEM_PROMPT",
    "check_grounding",
    "label_ai_generated",
    "RateLimiter",
    "verify_and_store_attestation",
    "MockAttestationVerifier",
    "ScaffoldAttestationVerifier",
    "set_default_verifier",
    "AttestationReport",
    "AuditMemo",
    "AuditMemoWriter",
    "make_memo",
    "tok",
]
