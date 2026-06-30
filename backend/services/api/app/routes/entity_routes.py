"""Entity-360 routes + audited PII unmask (BACKEND-19/17, blueprint Part 24.2 / 11 / 25.3).

GET /entities/{id} (+ /timeline /graph /peers) and POST /entities/{id}/unmask. Every entity view is
a who-viewed-whom audit event. Unmask is a SEPARATE, audited capability: Senior+ unconditional;
Analyst case-scoped (must justify, logged). De-tokenization reads the local re-id vault.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.rbac import decision
from app.pii.vault import VAULT
from app.schemas.common import Capability, Role
from app.schemas.entities import (
    EntityGraph,
    EntityProfile,
    EntityTimeline,
    PeerComparison,
    UnmaskRequest,
    UnmaskResponse,
)
from app.store.entity_store import ENTITIES

router = APIRouter(tags=["entities"])


def _view_audit(principal: Principal, entity_id: str, what: str) -> None:
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action=f"entity.{what}",
        target=entity_id,
    )


@router.get("/entities/{entity_id}", response_model=EntityProfile)
def get_entity(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> EntityProfile:
    profile = ENTITIES.get_profile(entity_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="entity not found")
    _view_audit(principal, entity_id, "view")
    return profile


@router.get("/entities/{entity_id}/timeline", response_model=EntityTimeline)
def get_timeline(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> EntityTimeline:
    if ENTITIES.get_profile(entity_id) is None:
        raise HTTPException(status_code=404, detail="entity not found")
    _view_audit(principal, entity_id, "timeline")
    return EntityTimeline(entity_id=entity_id, events=ENTITIES.get_timeline(entity_id))


@router.get("/entities/{entity_id}/graph", response_model=EntityGraph)
def get_graph(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> EntityGraph:
    graph = ENTITIES.get_graph(entity_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="entity graph not found")
    _view_audit(principal, entity_id, "graph")
    return graph


@router.get("/entities/{entity_id}/peers", response_model=list[PeerComparison])
def get_peers(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> list[PeerComparison]:
    if ENTITIES.get_profile(entity_id) is None:
        raise HTTPException(status_code=404, detail="entity not found")
    _view_audit(principal, entity_id, "peers")
    return ENTITIES.get_peers(entity_id)


@router.post("/entities/{entity_id}/unmask", response_model=UnmaskResponse)
def unmask(
    entity_id: str,
    body: UnmaskRequest,
    principal: Principal = Depends(require_capability(Capability.UNMASK_PII)),
) -> UnmaskResponse:
    """Re-identify tokenized PII (audited). Analyst must provide a justification (case-scoped)."""
    grant = decision(principal.role, Capability.UNMASK_PII)
    if (
        principal.role == Role.ANALYST
        and grant.note == "case_scoped_logged"
        and not body.justification
    ):
        raise HTTPException(
            status_code=403, detail="Analyst unmask requires a case-scoped justification"
        )

    tokens = body.tokens or VAULT.known_tokens()
    mapping = VAULT.resolve_many(tokens)
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="pii.unmask",
        target=entity_id,
        detail={"tokens": list(mapping.keys()), "justification": body.justification},
    )
    # NOTE: the mapping (real values) is returned to the authorized caller but is NEVER logged.
    return UnmaskResponse(entity_id=entity_id, mapping=mapping, audit_id=audit.audit_id)
