"""The narrate() gateway: primary -> secondary -> deterministic fallback (ML-10; Part 25.4-25.7).

Failover order (UI never breaks):
  (1) NEAR AI Cloud  (TEE, attestation verified)
  (2) Groq           (not a TEE path, tee_attested=false)
  (3) deterministic Jinja template from reason codes (no LLM, always works)

Every path writes an audit memo. LLM outputs are GROUNDED against the reason codes —
a narrative that introduces a fact not in evidence is rejected and we fail over.
Response shape (Part 25.6 / BACKEND.md §7): {narrative, provider, tee_attested, attestation_id, model}.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional, Sequence

from ml._optional import optional_import
from ml.narrative.attestation import verify_and_store_attestation
from ml.narrative.audit_memo import AuditMemoWriter, make_memo
from ml.narrative.guardrails import RateLimiter, check_grounding, label_ai_generated
from ml.narrative.providers import GroqProvider, LLMProvider, NearAIProvider

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Part 25.5 system prompt (verbatim intent): medium reasoning, factual, evidence-only, no de-anon.
SYSTEM_PROMPT = (
    "Reasoning: medium\n"
    "You are a bank fraud-investigation assistant. Write a concise, factual narrative of why this "
    "alert fired and what the investigator should verify. Use ONLY the provided evidence; never invent "
    "facts, names, or numbers. Identifiers are tokens (e.g., EMP-7f3a); do not try to de-anonymize them."
)


def _user_prompt(alert_ctx: dict[str, Any]) -> str:
    return f"Alert evidence (tokenized):\n{alert_ctx}"


def render_template(alert_ctx: dict[str, Any]) -> str:
    """Deterministic narrative from reason codes (no LLM). jinja2 if present, else pure-python."""
    ctx = _TemplateCtx(alert_ctx)
    jinja2 = optional_import("jinja2")
    tmpl_path = os.path.join(_TEMPLATE_DIR, "fallback.jinja")
    if jinja2 is not None and os.path.isfile(tmpl_path):
        with open(tmpl_path) as fh:
            return jinja2.Template(fh.read()).render(a=ctx).strip()
    # pure-python fallback
    rcs = " ".join(
        (rc.get("detail") or rc.get("code") or rc.get("feature") or "")
        for rc in ctx.reason_codes
    )
    return (
        f"Alert {ctx.alert_id} on entity {ctx.entity_id} fired at risk {ctx.risk_score}/100 "
        f"({ctx.severity}). Evidence: {rcs}. Recommended checks: verify the beneficiary, confirm "
        f"maker-checker independence, and obtain justification for off-hours activity. "
        f"(AI-generated · advisory only · not a decision.)"
    )


class _TemplateCtx:
    """Attribute access over an alert dict for the template (reason_codes as dicts)."""

    def __init__(self, alert_ctx: dict[str, Any]) -> None:
        self.alert_id = alert_ctx.get("alert_id", "n/a")
        self.entity_id = alert_ctx.get("entity_id", "n/a")
        self.risk_score = alert_ctx.get("risk_score", "n/a")
        self.severity = alert_ctx.get("severity", "n/a")
        self.confidence = alert_ctx.get("confidence")
        self.contributing_layers = alert_ctx.get("contributing_layers", []) or []
        self.reason_codes = [
            rc if isinstance(rc, dict) else getattr(rc, "to_dict", lambda: {})()
            for rc in (alert_ctx.get("reason_codes", []) or [])
        ]


def default_providers() -> list[LLMProvider]:
    return [NearAIProvider(), GroqProvider()]


def narrate(
    alert_ctx: dict[str, Any],
    *,
    providers: Optional[Sequence[LLMProvider]] = None,
    audit_writer: Optional[AuditMemoWriter] = None,
    rate_limiter: Optional[RateLimiter] = None,
    attestation_verifier=None,
) -> dict[str, Any]:
    """Generate a grounded narrative with full failover + audit. Never raises.

    Returns {narrative, provider, tee_attested, attestation_id, model} (+ ai_generated/advisory/label).
    """
    providers = list(providers) if providers is not None else default_providers()
    writer = audit_writer or AuditMemoWriter()
    user = _user_prompt(alert_ctx)
    alert_id = alert_ctx.get("alert_id")

    rate_limited = False
    if rate_limiter is not None and not rate_limiter.allow(
        str(alert_id or alert_ctx.get("entity_id", "global"))
    ):
        rate_limited = True  # skip LLMs, go straight to the deterministic template

    if not rate_limited:
        for prov in providers:
            if not prov.available():
                continue
            try:
                result = prov.complete(SYSTEM_PROMPT, user)
            except Exception:
                continue
            grounding = check_grounding(result.text, alert_ctx)
            if not grounding.grounded:
                # ungrounded -> reject this provider's output and fail over (Part 25.7)
                continue
            attestation_id = verify_and_store_attestation(
                prov.name, attestation_verifier
            )
            tee_attested = bool(prov.tee and attestation_id is not None)
            writer.write(
                make_memo(
                    provider=prov.name,
                    tee_attested=tee_attested,
                    attestation_id=attestation_id,
                    model=result.model,
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user,
                    alert_id=alert_id,
                )
            )
            return label_ai_generated(
                {
                    "narrative": result.text,
                    "provider": prov.name,
                    "tee_attested": tee_attested,
                    "attestation_id": attestation_id,
                    "model": result.model,
                    "ts": time.time(),
                    "grounding": grounding.to_dict(),
                }
            )

    # deterministic fallback — UI never breaks
    narrative = render_template(alert_ctx)
    writer.write(
        make_memo(
            provider="template",
            tee_attested=False,
            attestation_id=None,
            model=None,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user,
            alert_id=alert_id,
        )
    )
    return label_ai_generated(
        {
            "narrative": narrative,
            "provider": "template",
            "tee_attested": False,
            "attestation_id": None,
            "model": None,
            "ts": time.time(),
            "rate_limited": rate_limited,
        }
    )
