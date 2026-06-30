"""Groq provider — SECONDARY, NOT a TEE path (ML-11, SCAFFOLD; Part 25.4 #2)."""
from __future__ import annotations

from ml.narrative.providers.base import LLMProvider


class GroqProvider(LLMProvider):
    name = "groq"
    base_url = "https://api.groq.com/openai/v1"  # OpenAI-compatible
    env_key = "GROQ_API_KEY"
    tee = False  # audit memo records tee_attested=false (deliberate logged degradation)
