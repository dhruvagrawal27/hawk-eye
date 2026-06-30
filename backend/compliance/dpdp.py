"""Cross-border / DPDP transfer controls + data-principal rights (BACKEND-29, blueprint Part 28.1).

* PII is tokenized before egress with a TEE-attestation note (the actual tokenization lives in
  ``app.pii``; this records the transfer governance around it).
* Transfer documentation + destination-jurisdiction confirmation for any cross-border processing.
* Data-principal rights — access / correction / erasure / grievance — with response SLAs.

SCAFFOLD: TEE hardware attestation + legal destination-jurisdiction confirmation are external; the
workflow and SLA bookkeeping run REAL on synthetic data. Erasure honours the fraud-investigation
carve-out (records under active EDD/regulatory hold are not erased).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# DPDP response SLAs (calendar days) — illustrative defaults.
_SLA_DAYS = {"access": 30, "correction": 30, "erasure": 30, "grievance": 7}
_VALID_REQUESTS = set(_SLA_DAYS)


@dataclass
class TransferRecord:
    transfer_id: str
    purpose: str
    destination_jurisdiction: str
    pii_tokenized: bool
    tee_attested: bool
    jurisdiction_confirmed: bool  # SCAFFOLD: requires external legal confirmation
    notes: str = ""


@dataclass
class DataPrincipalRequest:
    request_id: str
    request_type: str  # access | correction | erasure | grievance
    principal_id: str
    status: str
    sla_days: int
    fraud_hold: bool = False  # erasure is refused while under active investigation/regulatory hold


@dataclass
class DpdpRegister:
    transfers: list[TransferRecord] = field(default_factory=list)
    requests: list[DataPrincipalRequest] = field(default_factory=list)

    def record_transfer(
        self, purpose: str, destination_jurisdiction: str, *, tee_attested: bool = False
    ) -> TransferRecord:
        rec = TransferRecord(
            transfer_id=f"xfer_{uuid.uuid4().hex[:6]}",
            purpose=purpose,
            destination_jurisdiction=destination_jurisdiction,
            pii_tokenized=True,  # PII is ALWAYS tokenized before egress (Part 25.3)
            tee_attested=tee_attested,
            jurisdiction_confirmed=False,  # SCAFFOLD — external legal confirmation pending
            notes="PII tokenized before egress; destination-jurisdiction confirmation pending (SCAFFOLD).",
        )
        self.transfers.append(rec)
        return rec

    def submit_request(
        self, request_type: str, principal_id: str, *, under_fraud_hold: bool = False
    ) -> DataPrincipalRequest:
        if request_type not in _VALID_REQUESTS:
            raise ValueError(f"unknown data-principal request type: {request_type}")
        # Erasure is refused (logged) while a record is under active investigation/regulatory hold.
        refused = request_type == "erasure" and under_fraud_hold
        req = DataPrincipalRequest(
            request_id=f"dpr_{uuid.uuid4().hex[:6]}",
            request_type=request_type,
            principal_id=principal_id,
            status="refused_fraud_carveout" if refused else "received",
            sla_days=_SLA_DAYS[request_type],
            fraud_hold=under_fraud_hold,
        )
        self.requests.append(req)
        return req


REGISTER = DpdpRegister()
