"""NEAR AI Cloud provider — PRIMARY, TEE-attested (ML-11, SCAFFOLD; Part 25.4 #1)."""
from __future__ import annotations

from ml.narrative.providers.base import LLMProvider


class NearAIProvider(LLMProvider):
    name = "near_ai"
    base_url = "https://cloud-api.near.ai/v1"  # gateway mode (TLS terminates inside the enclave)
    env_key = "NEAR_AI_API_KEY"
    tee = True  # attestation verified separately via ml.narrative.attestation
