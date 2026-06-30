"""DPDP / cross-border compliance routes (BACKEND-29, blueprint Part 28.1).

Compliance-only. Records cross-border transfer governance (PII tokenized before egress + jurisdiction
note) and intakes data-principal rights requests (access/correction/erasure/grievance) with SLAs.
SCAFFOLD: TEE attestation + legal jurisdiction confirmation are external.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.audit.writer import AUDIT
from app.auth.deps import require_role
from app.auth.principal import Principal
from app.schemas.common import Role
from compliance.dpdp import REGISTER

router = APIRouter(tags=["compliance"])

_COMPLIANCE = require_role(Role.COMPLIANCE_OFFICER, Role.TEAM_LEAD, Role.PLATFORM_ADMIN)


class TransferRequest(BaseModel):
    purpose: str
    destination_jurisdiction: str
    tee_attested: bool = False


class DataPrincipalRequestBody(BaseModel):
    request_type: str = Field(..., description="access | correction | erasure | grievance")
    principal_id: str
    under_fraud_hold: bool = False


@router.post("/compliance/transfers")
def record_transfer(body: TransferRequest, principal: Principal = Depends(_COMPLIANCE)) -> dict:
    rec = REGISTER.record_transfer(
        body.purpose, body.destination_jurisdiction, tee_attested=body.tee_attested
    )
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="dpdp.transfer",
        detail={"transfer_id": rec.transfer_id, "destination": rec.destination_jurisdiction},
    )
    return rec.__dict__


@router.post("/compliance/data-principal")
def data_principal_request(
    body: DataPrincipalRequestBody, principal: Principal = Depends(_COMPLIANCE)
) -> dict:
    try:
        req = REGISTER.submit_request(
            body.request_type, body.principal_id, under_fraud_hold=body.under_fraud_hold
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="dpdp.data_principal",
        target=body.principal_id,
        detail={"request_id": req.request_id, "type": req.request_type, "status": req.status},
    )
    return req.__dict__
