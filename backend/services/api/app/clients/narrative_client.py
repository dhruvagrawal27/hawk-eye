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
        if not settings.narrative_remote_enabled:
            return self._fallback(alert_ctx, ph)  # local/CI: deterministic template, no egress
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
