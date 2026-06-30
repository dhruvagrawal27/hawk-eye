"""TEE-attestation mock — FastAPI (PLATFORM-14, blueprint Part 25.2/25.4, MOCK).

Endpoints:
  POST /attest  {prompt, model, provider}  -> signed dual quote + audit memo
  POST /verify  {<attestation report>}      -> {valid, reasons}
  GET  /pubkey                              -> mock signing public key (hex)
  GET  /health, /metrics
Demo: request -> quote -> verify (`make` target / curl). Egress carries only tokenized
prompts; a raw-PII prompt is rejected (tokenize-before-egress, Part 25.3).
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

from . import attestation

ENCLAVE_MODE = os.environ.get("TEE_ENCLAVE_MODE", "true").lower() == "true"
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "openai/gpt-oss-120b")

app = FastAPI(title="hawk-eye tee-attestation (MOCK)", version="1.0.0")
ATTEST = Counter("tee_attest_total", "attestations issued", ["provider", "result"])
VERIFY = Counter("tee_verify_total", "verifications", ["result"])


class AttestRequest(BaseModel):
    prompt: str                       # MUST be tokenized already (Part 25.3)
    model: str = DEFAULT_MODEL
    provider: str = "near_ai"         # near_ai (TEE) | groq (non-TEE)


@app.get("/health")
def health():
    return {"status": "ok", "service": "tee-attestation", "enclave_mode": ENCLAVE_MODE, "mock": True}


@app.get("/pubkey")
def pubkey():
    return {"algorithm": "ed25519", "public_key_hex": attestation.public_key_hex(), "mock": True}


@app.post("/attest")
def attest(req: AttestRequest):
    # Groq is not a TEE path (Part 25.4): record tee_attested=false, still tokenize.
    if req.provider == "groq":
        if attestation.pii_leak(req.prompt):
            ATTEST.labels("groq", "pii_rejected").inc()
            raise HTTPException(422, "PII not tokenized before egress; refusing")
        ATTEST.labels("groq", "non_tee").inc()
        return {"provider": "groq", "tee_attested": False, "attestation_id": None,
                "model": req.model, "pii_tokenized": True,
                "note": "Groq is not a TEE path (Part 25.4); logged degradation."}
    try:
        report = attestation.issue_quote(req.prompt, req.model, req.provider, ENCLAVE_MODE)
    except ValueError as e:
        ATTEST.labels(req.provider, "pii_rejected").inc()
        raise HTTPException(422, str(e))
    ATTEST.labels(req.provider, "issued").inc()
    return report


@app.post("/verify")
def verify(report: dict):
    result = attestation.verify_quote(report)
    VERIFY.labels("valid" if result["valid"] else "invalid").inc()
    return result


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
