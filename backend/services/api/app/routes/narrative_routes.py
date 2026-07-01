"""Narrative route (BACKEND-20-adjacent, blueprint Part 25.4).

POST /narratives/{alert_id} (Analyst+). Assembles TOKENIZED alert context, calls ML's narrate()
gateway (NEAR AI → Groq → deterministic template — UI never breaks), and persists the audit memo
(provider / tee_attested / attestation_id / model / prompt_hash / ts). BACKEND owns the route + the
memo write; ML owns the gateway/fallback; PLATFORM owns egress + the TEE-attestation MOCK.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.clients.narrative_client import NARRATIVE_CLIENT
from app.pii.tokenizer import tokenize_payload
from app.pii.vault import VAULT
from app.schemas.common import Capability
from app.schemas.narratives import NarrativeAuditMemo, NarrativeResponse
from app.store.alert_store import ALERTS

router = APIRouter(tags=["narratives"])


@router.post("/narratives/{alert_id}", response_model=NarrativeResponse)
def generate_narrative(
    alert_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> NarrativeResponse:
    alert = ALERTS.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")

    # Assemble context and tokenize BEFORE egress (defense-in-depth; alert is already tokenized).
    context = {
        "alert_id": alert.alert_id,
        "entity_id": alert.entity_id,
        "risk_score": alert.risk_score,
        "severity": str(alert.severity),
        "reason_codes": [rc.model_dump(exclude_none=True) for rc in alert.reason_codes],
    }
    context = tokenize_payload(context, vault=VAULT)

    result = NARRATIVE_CLIENT.narrate(context)  # tries ML gateway → deterministic fallback

    memo = NarrativeAuditMemo(
        alert_id=alert_id,
        provider=result["provider"],
        tee_attested=result["tee_attested"],
        attestation_id=result["attestation_id"],
        model=result["model"],
        prompt_hash=result["prompt_hash"],
        ts=result["ts"],
    )
    ALERTS.add_narrative_memo(memo)
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="narrative.generate",
        target=alert.entity_id,
        detail={
            "alert_id": alert_id,
            "provider": memo.provider,
            "tee_attested": memo.tee_attested,
            "prompt_hash": memo.prompt_hash,
        },
    )
    return NarrativeResponse(
        alert_id=alert_id,
        narrative=result["narrative"],
        provider=result["provider"],
        tee_attested=result["tee_attested"],
        attestation_id=result["attestation_id"],
        model=result["model"],
        ai_generated=True,
    )


@router.get("/narratives/{alert_id}/attestation")
def get_attestation(
    alert_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> dict:
    """Real NEAR AI Cloud TEE attestation for the confidential-compute claim (Intel TDX enclave
    signing address + quote fingerprint). Powers the ProvenanceBadge; degrades honestly when the
    gateway is local-only or unreachable."""
    return NARRATIVE_CLIENT.get_attestation(alert_id)
