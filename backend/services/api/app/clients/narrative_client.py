"""Narrative gateway client (BACKEND-20-adjacent seam, blueprint Part 25.4/25.5).

# STUB: ML (owns ``narrate()``: NEAR AI primary → Groq secondary → deterministic Jinja fallback).
BACKEND exposes ``POST /narratives/{alert_id}`` and calls ML's gateway with **tokenized** context.
ML owns the failover; PLATFORM owns egress + secrets + the TEE-attestation MOCK. This client tries
the ML gateway over HTTP and, if it is unreachable, renders the SAME deterministic Jinja template
locally so the route NEVER breaks (the UI never goes dark). Raw PII is asserted-out before egress.
"""

from __future__ import annotations

import hashlib
import json

import httpx
from jinja2 import Template

from app.config import settings
from app.pii.tokenizer import assert_no_raw_pii
from app.schemas.common import iso_z, utcnow

# Deterministic fallback (Part 25.5) — structured narrative from reason codes, no LLM.
_FALLBACK_TMPL = Template(
    "Alert {{ a.alert_id }} (risk {{ a.risk_score }}, {{ a.severity }}): "
    "{% for r in a.reason_codes %}{{ r.detail or r.code }}. {% endfor %}"
    "Recommended checks: verify the beneficiary is independently onboarded, confirm "
    "maker-checker independence, and obtain justification for any off-hours activity."
)

_SYSTEM_PROMPT = (
    "You are a bank fraud-investigation assistant for a public-sector bank in India. "
    "Given a TOKENIZED alert context (all PII is already pseudonymized — never invent real names, "
    "accounts, or amounts), write a concise, factual investigation narrative for a human analyst: "
    "what the detectors flagged, why it is suspicious, and the concrete checks to perform. "
    "3-5 sentences, regulator-defensible tone, no markdown, no speculation beyond the evidence."
)


def prompt_hash(ctx: dict) -> str:
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(ctx, sort_keys=True, default=str).encode("utf-8")).hexdigest()[
            :16
        ]
    )


class NarrativeClient:
    def __init__(self, gateway_url: str | None = None):
        self.gateway_url = gateway_url or settings.narrative_url

    def narrate(self, alert_ctx: dict, *, timeout: float | None = None) -> dict:
        """Return a narrative + audit-memo fields. Context MUST already be PII-tokenized."""
        assert_no_raw_pii(alert_ctx)  # hard guard: nothing raw leaves the perimeter
        if timeout is None:
            timeout = settings.narrative_timeout_seconds
        ph = prompt_hash(alert_ctx)
        if not self._remote_enabled():
            return self._fallback(alert_ctx, ph)  # local/CI: deterministic template, no egress

        # 1) Direct in-process providers (NEAR AI primary → Groq) over the OpenAI-compatible SDK.
        direct = self._remote_direct(alert_ctx, ph, timeout)
        if direct is not None:
            return direct

        # 2) ML's HTTP gateway, if configured/reachable; else the deterministic template.
        try:  # pragma: no cover - ML gateway not running locally
            resp = httpx.post(self.gateway_url, json={"alert_ctx": alert_ctx}, timeout=timeout)
            resp.raise_for_status()
            body = resp.json()
            return {
                "narrative": body["narrative"],
                "provider": body.get("provider", "near_ai"),
                "tee_attested": bool(body.get("tee_attested", False)),
                "attestation_id": body.get("attestation_id"),
                "model": body.get("model"),
                "prompt_hash": ph,
                "ts": iso_z(utcnow()),
            }
        except Exception:
            return self._fallback(alert_ctx, ph)

    @staticmethod
    def _remote_enabled() -> bool:
        """Egress is on when explicitly enabled, or implicitly when a direct provider + key are
        configured in .env (so near.ai works locally without standing up the ML gateway)."""
        if settings.narrative_remote_enabled:
            return True
        prov = (settings.llm_provider or "").lower()
        if prov in ("nearai", "near_ai") and settings.near_ai_api_key:
            return True
        return bool(prov == "groq" and settings.groq_api_key)

    @staticmethod
    def _provider_chain() -> list[tuple[str, str, str, str]]:
        """(provider, base_url, api_key, model) tuples to try in order — NEAR AI primary, Groq next.
        Only providers with a configured key are included; honours an explicit ``groq`` preference.
        """
        chain: list[tuple[str, str, str, str]] = []
        if settings.near_ai_api_key:
            chain.append(
                (
                    "near_ai",
                    settings.near_ai_base_url,
                    settings.near_ai_api_key,
                    settings.near_ai_model,
                )
            )
        if settings.groq_api_key:
            chain.append(
                ("groq", settings.groq_base_url, settings.groq_api_key, settings.groq_model)
            )
        if (settings.llm_provider or "").lower() == "groq":
            chain.sort(key=lambda c: 0 if c[0] == "groq" else 1)
        return chain

    def _remote_direct(self, alert_ctx: dict, ph: str, timeout: float) -> dict | None:
        """Try each configured provider in order via the OpenAI-compatible SDK. Returns the narrative
        dict on the first success, or None if no provider is configured / all fail (→ gateway/template).
        The ``openai`` package is an optional dep; if it isn't importable we quietly fall through.
        """
        chain = self._provider_chain()
        if not chain:
            return None
        prompt = self._build_prompt(alert_ctx)
        for provider, base_url, api_key, model in chain:
            try:  # pragma: no cover - needs live provider + network
                from openai import OpenAI

                client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                text = (resp.choices[0].message.content or "").strip()
                if not text:
                    continue
                return {
                    "narrative": text,
                    "provider": provider,
                    # TEE proof is fetched separately (get_attestation); narrate() reports it honestly
                    # as unproven here rather than asserting a TEE it hasn't verified.
                    "tee_attested": False,
                    "attestation_id": None,
                    "model": model,
                    "prompt_hash": ph,
                    "ts": iso_z(utcnow()),
                }
            except Exception:
                continue
        return None

    @staticmethod
    def _build_prompt(alert_ctx: dict) -> str:
        """Render the tokenized alert context into a compact user prompt (PII already pseudonymized)."""
        reasons = "; ".join(
            str(r.get("detail") or r.get("code") or "") for r in alert_ctx.get("reason_codes", [])
        )
        return (
            f"Alert {alert_ctx.get('alert_id')} on entity {alert_ctx.get('entity_id')}. "
            f"Fused risk score {alert_ctx.get('risk_score')} / 100 (severity {alert_ctx.get('severity')}). "
            f"Detector findings: {reasons or 'none provided'}. "
            "Write the investigation narrative and the checks to perform."
        )

    def get_attestation(self, alert_id: str, *, timeout: float | None = None) -> dict:
        """Fetch the REAL NEAR AI Cloud TEE attestation from the gateway (Intel TDX enclave proof).
        Free endpoint (no inference credit needed). Returns a not-attested detail if the gateway is
        local-only or unreachable — the UI degrades honestly."""
        if timeout is None:
            timeout = settings.narrative_timeout_seconds
        not_attested = {
            "alert_id": alert_id,
            "tee_attested": False,
            "provider": "near_ai",
            "model": "openai/gpt-oss-120b",
        }
        if not settings.narrative_remote_enabled:
            return not_attested
        base = self.gateway_url.rsplit("/narrate", 1)[0]
        try:  # pragma: no cover - needs the live gateway
            resp = httpx.get(f"{base}/attestation", timeout=timeout)
            resp.raise_for_status()
            b = resp.json()
            if not b.get("tee_attested"):
                return not_attested
            return {
                "alert_id": alert_id,
                "tee_attested": True,
                "provider": b.get("provider", "near_ai"),
                "gateway": "near-ai-confidential (cloud-api.near.ai)",
                "model": "openai/gpt-oss-120b",
                "signing_address": b.get("signing_address"),
                "signing_algo": b.get("signing_algo"),
                "intel_quote_sha256": b.get("intel_quote_sha256"),
                "attestation_id": b.get("attestation_id"),
                "verified_ts": iso_z(utcnow()),
                "extra": [
                    {
                        "label": "Intel TDX quote",
                        "value": f"{b.get('intel_quote_bytes', 0)} bytes · {b.get('intel_quote_prefix', '')}…",
                    },
                    {"label": "NVIDIA GPU attested", "value": str(b.get("nvidia_verified", False))},
                ],
            }
        except Exception:
            return not_attested

    def _fallback(self, alert_ctx: dict, ph: str) -> dict:
        return {
            "narrative": _FALLBACK_TMPL.render(a=alert_ctx),
            "provider": "template",
            "tee_attested": False,
            "attestation_id": None,
            "model": None,
            "prompt_hash": ph,
            "ts": iso_z(utcnow()),
        }


NARRATIVE_CLIENT = NarrativeClient()
