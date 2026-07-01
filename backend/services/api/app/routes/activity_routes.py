"""Ambient / sub-threshold activity route — surfaces the 'hidden 95%'.

GET /activity/sub-threshold → the detection funnel (scored → sub-threshold → alerted) plus a
watchlist of elevated-but-not-alerted entities (fused score 40–69, under the EMIT_THRESHOLD of 70).
This is the population the alert queue never shows: near-misses and slow-drift actors. Alert-only,
read, audited — it never creates alerts, it just makes the silent majority visible.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.activity import SubThresholdResponse
from app.schemas.common import Capability
from app.store.subthreshold_store import SUBTHRESHOLD

router = APIRouter(tags=["activity"])


@router.get("/activity/sub-threshold", response_model=SubThresholdResponse)
def get_sub_threshold(
    limit: int = 20,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> SubThresholdResponse:
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="activity.sub_threshold",
        target="__population__",
        detail={"limit": limit},
    )
    return SubThresholdResponse(**SUBTHRESHOLD.snapshot(watch_limit=max(1, min(100, limit))))
