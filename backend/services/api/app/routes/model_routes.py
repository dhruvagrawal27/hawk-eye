"""Model / drift / metrics routes (BACKEND-21, blueprint Part 24.2 l.909-910).

GET /models, POST /models/{id}/promote (Model-Eng + second-person sign-off, SoD-checked), GET /drift,
GET /metrics/model. Promotion verifies the artifact signature and canary hot-swaps (BACKEND-16).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.sod import SoDError, check_promotion_signoff
from app.clients.registry_client import REGISTRY_CLIENT
from app.schemas.common import Capability, Role
from app.schemas.models import (
    DriftReport,
    ModelInfo,
    ModelQuality,
    PromoteRequest,
    PromoteResult,
)
from serving.loader import SignatureError

router = APIRouter(tags=["models"])


@router.get("/models", response_model=list[ModelInfo])
def list_models(
    principal: Principal = Depends(require_capability(Capability.TRAIN_DEPLOY_MODELS)),
) -> list[ModelInfo]:
    return [
        ModelInfo(
            model_id=a.model_id,
            layer=a.layer,
            version=a.version,
            stage=a.stage,
            signed=a.signed_valid,
            training_data_hash=a.training_data_hash,
            feature_set_version=a.feature_set_version,
            approving_reviewer=a.approving_reviewer,
            metrics=a.metrics,
        )
        for a in REGISTRY_CLIENT.list_models()
    ]


@router.post("/models/{model_id}/promote", response_model=PromoteResult)
def promote_model(
    model_id: str,
    body: PromoteRequest,
    version: str = Query(..., description="Artifact version to promote"),
    principal: Principal = Depends(require_capability(Capability.TRAIN_DEPLOY_MODELS)),
) -> PromoteResult:
    # Only the Model Engineer promotes models (Part 24.1: ✅ with sign-off). Platform Admin's
    # train/deploy is ⚠️ deploy-infra-only — it does not extend to promoting a model artifact.
    if principal.role != Role.MODEL_ENGINEER:
        raise HTTPException(
            status_code=403,
            detail=f"model promotion is a Model Engineer action; role {principal.role.value} "
            "may deploy infra but not promote models",
        )
    # SoD: promotion requires a second-person sign-off (promoter ≠ approver) — Part 24.1.
    try:
        check_promotion_signoff(principal.user_id, body.signoff_by)
    except SoDError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        res = REGISTRY_CLIENT.promote(model_id, version, body.to_stage, body.canary_percent)
    except SignatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="model.promote",
        target=model_id,
        detail={
            "version": version,
            "stage": body.to_stage,
            "signoff_by": body.signoff_by,
            "canary_percent": body.canary_percent,
        },
    )
    return PromoteResult(
        model_id=model_id,
        version=version,
        stage=body.to_stage,
        canary_percent=res["canary_percent"],
        signature_verified=res["signature_verified"],
        audit_id=audit.audit_id,
    )


@router.get("/drift", response_model=DriftReport)
def drift(
    model_id: str = Query("l3_lightgbm"),
    principal: Principal = Depends(require_capability(Capability.TRAIN_DEPLOY_MODELS)),
) -> DriftReport:
    return DriftReport(**REGISTRY_CLIENT.drift(model_id))


@router.get("/metrics/model", response_model=ModelQuality)
def model_metrics(
    model_id: str = Query("l3_lightgbm"),
    principal: Principal = Depends(require_capability(Capability.TRAIN_DEPLOY_MODELS)),
) -> ModelQuality:
    return ModelQuality(**REGISTRY_CLIENT.quality(model_id))
