"""LLM providers for the narrative gateway: NEAR AI (primary, TEE) -> Groq (secondary)."""
from __future__ import annotations

from ml.narrative.providers.base import MAX_TOKENS, MODEL, TEMPERATURE, LLMProvider, ProviderResult
from ml.narrative.providers.groq import GroqProvider
from ml.narrative.providers.near_ai import NearAIProvider

__all__ = ["LLMProvider", "ProviderResult", "NearAIProvider", "GroqProvider", "MODEL", "TEMPERATURE", "MAX_TOKENS"]
