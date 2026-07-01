"""Management analytics route — fraud-typology prevalence + confirmed-rate (portfolio oversight).

GET /analytics/typologies → per-typology alert volume, human-confirmed vs cleared, confirmed-rate,
and exposure — the "which insider typologies are actually firing, and how often are they real?"
view for management / vigilance. Read-only, audited.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.analytics import TypologyAnalyticsResponse
from app.schemas.common import Capability
from app.store.analytics_store import ANALYTICS

router = APIRouter(tags=["analytics"])


@router.get("/analytics/typologies", response_model=TypologyAnalyticsResponse)
def get_typology_analytics(
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> TypologyAnalyticsResponse:
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="analytics.typologies",
        target="__portfolio__",
        detail={},
    )
    return TypologyAnalyticsResponse(**ANALYTICS.typology_snapshot())
