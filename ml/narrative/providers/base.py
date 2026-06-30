"""OpenAI-compatible LLM provider base for the narrative gateway (ML-11).

# SCAFFOLD: real calls need live API keys (injected by PLATFORM secrets). With no key
# present the provider reports unavailable and the gateway fails over to the next
# provider, then to the deterministic template — the UI never breaks. Keys are read
# from os.environ and NEVER hardcoded (golden rule #2).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

from ml._optional import optional_import

MODEL = "openai/gpt-oss-120b"  # Part 25.4: same model across NEAR AI + Groq
TEMPERATURE = 0.2
MAX_TOKENS = 500


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    tee: bool


class LLMProvider:
    """An OpenAI-compatible chat provider (NEAR AI / Groq)."""

    name: str = "base"
    base_url: str = ""
    env_key: str = ""
    tee: bool = False
    model: str = MODEL

    def __init__(self, *, timeout: float = 20.0, max_retries: int = 2) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.env_key)

    def available(self) -> bool:
        """True iff the OpenAI SDK is installed AND a key is present (else we fail over)."""
        return optional_import("openai") is not None and bool(self.api_key())

    def _client(self):
        openai = optional_import("openai")
        if openai is None:
            raise ImportError("openai SDK not installed")
        key = self.api_key()
        if not key:
            raise RuntimeError(f"{self.env_key} not set")
        return openai.OpenAI(base_url=self.base_url, api_key=key, timeout=self.timeout)

    def complete(self, system: str, user: str) -> ProviderResult:
        """Call the model with retries. Raises on failure (gateway catches and fails over)."""
        client = self._client()
        last: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = client.chat.completions.create(
                    model=self.model,
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return ProviderResult(
                    text=r.choices[0].message.content or "",
                    provider=self.name,
                    model=self.model,
                    tee=self.tee,
                )
            except Exception as exc:  # pragma: no cover - needs live API
                last = exc
                # Permanent client errors (bad request / auth / quota / not-found) will not
                # recover on retry — fail over to the next provider immediately so the chain
                # stays fast even when this key is mis-set or out of credit (402 spend cap).
                status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                if status in (400, 401, 402, 403, 404):
                    break
                if attempt < self.max_retries:
                    time.sleep(0.2 * (attempt + 1))
        raise RuntimeError(
            f"{self.name} failed after {self.max_retries + 1} attempts: {last}"
        )
