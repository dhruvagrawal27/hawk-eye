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

    def narrate(self, alert_ctx: dict, *, timeout: float = 2.0) -> dict:
        """Return a narrative + audit-memo fields. Context MUST already be PII-tokenized."""
        assert_no_raw_pii(alert_ctx)  # hard guard: nothing raw leaves the perimeter
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
