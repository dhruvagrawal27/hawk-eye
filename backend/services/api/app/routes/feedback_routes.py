"""Active-learning feedback route (BACKEND-20, blueprint Part 24.2 l.911).

POST /feedback — submit a label to the feedback loop (DATA label-source-4 / ML retraining). Alert-
only: this is a human label, never an auto-classification. Writes an audit event.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.common import Capability
from app.schemas.disposition import FeedbackRequest, FeedbackResponse
from app.store.alert_store import ALERTS

router = APIRouter(tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    body: FeedbackRequest,
    principal: Principal = Depends(require_capability(Capability.DISPOSITION)),
) -> FeedbackResponse:
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="feedback.submit",
        target=body.alert_id,
        detail={"label": body.label.value, "confidence": body.confidence},
    )
    ALERTS.queue_feedback(
        {
            "alert_id": body.alert_id,
            "label": body.label.value,
            "confidence": body.confidence,
            "notes": body.notes,
            "labeled_by": principal.user_id,
            "audit_id": audit.audit_id,
            "source": "active_learning_feedback",
        }
    )
    return FeedbackResponse(
        accepted=True,
        label_written=True,
        feedback_queued_for_retraining=True,
        audit_id=audit.audit_id,
    )
