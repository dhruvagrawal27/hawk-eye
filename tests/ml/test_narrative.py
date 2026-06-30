"""Narrative-gateway tests: ML-10 (failover/template), ML-11 (providers), ML-12 (attestation/
audit/guardrails), ML-13 (POST /narratives). Blueprint Part 25.4-25.7, BACKEND.md §7."""

from __future__ import annotations

import os


from ml.narrative import (
    AuditMemoWriter,
    MockAttestationVerifier,
    RateLimiter,
    check_grounding,
    narrate,
    render_template,
    tok,
)
from ml.narrative.providers import GroqProvider, NearAIProvider
from ml.narrative.providers.base import LLMProvider, ProviderResult

ALERT_CTX = {
    "alert_id": "alr_3d7e22",
    "entity_id": "EMP-7f3a",
    "risk_score": 87,
    "severity": "high",
    "confidence": 0.82,
    "contributing_layers": ["L1_rules", "L2_unsupervised", "L3_gbdt", "L5_graph"],
    "reason_codes": [
        {
            "source": "rule",
            "code": "NEW_BENEFICIARY_THEN_HIGHVALUE",
            "detail": "new payee BEN-9b1c paid INR 4800000 within 27 min",
        },
        {
            "source": "shap",
            "feature": "new_beneficiary_to_payment_latency_min",
            "contribution": 0.31,
        },
        {
            "source": "graph",
            "detail": "maker EMP-7f3a + checker EMP-1a09 recur as isolated pair (ring RNG-12)",
        },
    ],
    "exposure_inr": 4800000,
    "pii_tokenized": True,
}

RESPONSE_KEYS = {"narrative", "provider", "tee_attested", "attestation_id", "model"}


class _GroundedFake(LLMProvider):
    name = "near_ai"
    tee = True

    def available(self):
        return True

    def complete(self, system, user):
        text = (
            "Maker EMP-7f3a created new payee BEN-9b1c and approved INR 4800000 within 27 minutes; "
            "checker EMP-1a09 recurs with them as ring RNG-12. Risk 87."
        )
        return ProviderResult(
            text=text, provider=self.name, model="openai/gpt-oss-120b", tee=True
        )


class _UngroundedFake(LLMProvider):
    name = "near_ai"
    tee = True

    def available(self):
        return True

    def complete(self, system, user):
        # introduces a fabricated token + a large fabricated number not in evidence
        return ProviderResult(
            text="Fabricated payee EMP-dead99 moved 98765432 to an offshore account.",
            provider=self.name,
            model="openai/gpt-oss-120b",
            tee=True,
        )


# ----------------------------- ML-10 ----------------------------- #
def test_template_fallback_without_keys(tmp_path):
    # No keys -> providers unavailable -> deterministic template, UI never breaks.
    for k in ("NEAR_AI_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    w = AuditMemoWriter(path=str(tmp_path / "audit.jsonl"))
    out = narrate(ALERT_CTX, audit_writer=w)
    assert RESPONSE_KEYS <= set(out)
    assert (
        out["provider"] == "template"
        and out["tee_attested"] is False
        and out["model"] is None
    )
    assert "alr_3d7e22" in out["narrative"] and "BEN-9b1c" in out["narrative"]
    assert out["ai_generated"] is True and out["advisory"] is True


def test_render_template_is_grounded():
    text = render_template(ALERT_CTX)
    assert check_grounding(text, ALERT_CTX).grounded


# ----------------------------- ML-11 ----------------------------- #
def test_providers_wired_per_blueprint():
    near, groq = NearAIProvider(), GroqProvider()
    assert (
        near.base_url == "https://cloud-api.near.ai/v1"
        and near.tee is True
        and near.env_key == "NEAR_AI_API_KEY"
    )
    assert (
        groq.base_url == "https://api.groq.com/openai/v1"
        and groq.tee is False
        and groq.env_key == "GROQ_API_KEY"
    )
    assert near.model == "openai/gpt-oss-120b" == groq.model


def test_no_hardcoded_keys():
    for k in ("NEAR_AI_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    assert NearAIProvider().api_key() is None and not NearAIProvider().available()


# ----------------------------- ML-12 ----------------------------- #
def test_grounded_llm_path_with_attestation(tmp_path):
    w = AuditMemoWriter(path=str(tmp_path / "audit.jsonl"))
    out = narrate(
        ALERT_CTX,
        providers=[_GroundedFake()],
        audit_writer=w,
        attestation_verifier=MockAttestationVerifier(),
    )
    assert out["provider"] == "near_ai" and out["tee_attested"] is True
    assert isinstance(out["attestation_id"], str) and out["attestation_id"].startswith(
        "att_"
    )
    memos = w.all()
    assert (
        len(memos) == 1
        and memos[0]["provider"] == "near_ai"
        and memos[0]["prompt_hash"]
    )


def test_ungrounded_output_is_rejected_and_fails_over(tmp_path):
    w = AuditMemoWriter(path=str(tmp_path / "audit.jsonl"))
    out = narrate(
        ALERT_CTX,
        providers=[_UngroundedFake()],
        audit_writer=w,
        attestation_verifier=MockAttestationVerifier(),
    )
    # ungrounded LLM output rejected -> falls over to the deterministic template
    assert out["provider"] == "template"


def test_grounding_flags_invented_facts():
    res = check_grounding("Payee EMP-dead99 moved 98765432.", ALERT_CTX)
    assert not res.grounded
    assert (
        "EMP-dead99" in res.ungrounded_tokens and "98765432" in res.ungrounded_numbers
    )


def test_audit_memo_written_for_every_narrative(tmp_path):
    w = AuditMemoWriter(path=str(tmp_path / "audit.jsonl"))
    narrate(ALERT_CTX, audit_writer=w)
    narrate(ALERT_CTX, audit_writer=w)
    assert len(w.all()) == 2


def test_rate_limiter():
    rl = RateLimiter(max_calls=2, per_seconds=60.0)
    assert rl.allow("k") and rl.allow("k") and not rl.allow("k")


def test_tok_is_deterministic_and_prefixed():
    assert tok("Asha Rao", "EMP") == tok("Asha Rao", "EMP")
    assert tok("Asha Rao", "EMP").startswith("EMP-")


# ----------------------------- ML-13 ----------------------------- #
def test_post_narratives_contract():
    from fastapi.testclient import TestClient

    from ml.narrative.api import create_app

    for k in ("NEAR_AI_API_KEY", "GROQ_API_KEY"):
        os.environ.pop(k, None)
    client = TestClient(create_app())
    body = {k: v for k, v in ALERT_CTX.items() if k != "alert_id"}
    resp = client.post("/api/v1/narratives/alr_3d7e22", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert RESPONSE_KEYS <= set(data)
    assert data["provider"] == "template"  # no keys in CI
