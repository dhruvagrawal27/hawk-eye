"""Change-controlled rule/threshold CRUD with four-eyes (BACKEND-8, blueprint Part 24.2 / 31.3).

/rules is restricted to Compliance (TUNE_RULES). A change is a *proposal* that takes effect only
after a SECOND approver (≠ proposer) signs off (four-eyes). Every change is versioned and writes an
audit event. A rule change can blind detection — it is treated like a model change.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.sod import SoDError, check_four_eyes, check_rule_tuning
from app.schemas.common import Capability, Role, Severity
from app.schemas.rules import (
    RuleApproval,
    RuleApprovalResult,
    RuleChangeProposal,
    RuleChangeRequest,
    RuleSummary,
)
from app.store.alert_store import ALERTS
from app.store.rule_change_store import RULE_CHANGES
from rules_engine.engine import DEFAULT_ENGINE
from rules_engine.rule import RuleConfig

router = APIRouter(tags=["rules"])


def _alerts_generated_by(code: str) -> set[str]:
    """Alert ids whose reason codes include this rule — used by the SoD self-tuning guard."""
    return {a.alert_id for a in ALERTS.all() if any(rc.code == code for rc in a.reason_codes)}


def _guard_self_tuning(principal: Principal, code: str) -> None:
    """SoD (Part 19.6): an investigator may not tune the rules that generate their own alerts."""
    try:
        check_rule_tuning(principal, _alerts_generated_by(code))
    except SoDError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _bump_version(version: str) -> str:
    parts = (version.split(".") + ["0", "0", "0"])[:3]
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError:
        return version + ".1"
    return f"{major}.{minor}.{patch + 1}"


def _summary(cfg: RuleConfig) -> RuleSummary:
    return RuleSummary(
        code=cfg.code,
        name=cfg.name,
        version=cfg.version,
        enabled=cfg.enabled,
        severity=Severity(cfg.severity),
        hard_hit=cfg.hard_hit,
        description=cfg.description,
        params=cfg.params,
    )


@router.get("/rules", response_model=list[RuleSummary])
def list_rules(
    principal: Principal = Depends(require_capability(Capability.TUNE_RULES)),
) -> list[RuleSummary]:
    return [_summary(c) for c in DEFAULT_ENGINE.list_rules()]


@router.post("/rules", response_model=RuleChangeProposal, status_code=201)
def propose_rule_change(
    body: RuleChangeRequest,
    principal: Principal = Depends(require_capability(Capability.TUNE_RULES)),
) -> RuleChangeProposal:
    """Propose a rule/threshold change. Pending until a second approver signs off (four-eyes)."""
    if DEFAULT_ENGINE.get_rule(body.code) is None and body.name is None:
        raise HTTPException(
            status_code=404, detail=f"unknown rule {body.code} (provide name to create)"
        )
    _guard_self_tuning(principal, body.code)  # SoD: no tuning the rules that fire your own alerts
    diff = body.model_dump(exclude_none=True, exclude={"code", "change_reason"})
    proposal = RULE_CHANGES.create(body.code, principal.user_id, diff, body.change_reason)
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="rule.change_proposed",
        target=body.code,
        detail={"change_id": proposal.change_id, "diff": diff, "reason": body.change_reason},
    )
    return RuleChangeProposal(
        change_id=proposal.change_id,
        code=body.code,
        proposed_by=principal.user_id,
        status="pending_approval",
        diff=diff,
        audit_id=audit.audit_id,
    )


@router.put("/rules/{code}", response_model=RuleChangeProposal, status_code=201)
def update_rule_change(
    code: str,
    body: RuleChangeRequest,
    principal: Principal = Depends(require_capability(Capability.TUNE_RULES)),
) -> RuleChangeProposal:
    """PUT = propose an *update* to an existing rule (Part 24.2 `PUT /rules`). Like POST, it is a
    four-eyes proposal: it takes effect only after a second approver signs off, is versioned, and
    is audited. The rule code is taken from the path."""
    if DEFAULT_ENGINE.get_rule(code) is None:
        raise HTTPException(status_code=404, detail=f"unknown rule {code}")
    _guard_self_tuning(principal, code)  # SoD: no tuning the rules that fire your own alerts
    diff = body.model_dump(exclude_none=True, exclude={"code", "change_reason"})
    proposal = RULE_CHANGES.create(code, principal.user_id, diff, body.change_reason)
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="rule.change_proposed",
        target=code,
        detail={
            "change_id": proposal.change_id,
            "diff": diff,
            "reason": body.change_reason,
            "via": "PUT",
        },
    )
    return RuleChangeProposal(
        change_id=proposal.change_id,
        code=code,
        proposed_by=principal.user_id,
        status="pending_approval",
        diff=diff,
        audit_id=audit.audit_id,
    )


@router.post("/rules/{change_id}/approve", response_model=RuleApprovalResult)
def approve_rule_change(
    change_id: str,
    body: RuleApproval,
    principal: Principal = Depends(require_capability(Capability.TUNE_RULES)),
) -> RuleApprovalResult:
    proposal = RULE_CHANGES.get(change_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="change proposal not found")
    if proposal.status != "pending_approval":
        raise HTTPException(status_code=409, detail=f"change already {proposal.status}")

    # Only the DGM — Risk & Compliance is the change-controlled authority that may APPROVE (Part
    # 24.1: DGM Compliance = ✅ change-controlled; AGM Vigilance = ⚠️ propose-only). Others may
    # propose, not approve.
    if principal.role != Role.DGM_COMPLIANCE:
        raise HTTPException(
            status_code=403,
            detail="rule changes are approved by the DGM — Risk & Compliance (change-controlled); "
            f"role {principal.role.value} may propose but not approve",
        )
    # Four-eyes: the approver must differ from the proposer (Part 31.3).
    try:
        check_four_eyes(proposal.proposed_by, principal.user_id)
    except SoDError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if not body.approve:
        RULE_CHANGES.resolve(change_id, principal.user_id, False, None)
        AUDIT.write(
            actor=principal.user_id,
            actor_role=principal.role,
            action="rule.change_rejected",
            target=proposal.code,
            detail={"change_id": change_id},
        )
        return RuleApprovalResult(
            change_id=change_id,
            code=proposal.code,
            status="rejected",
            new_version=None,
            audit_id="",
        )

    existing = DEFAULT_ENGINE.get_rule(proposal.code)
    base = existing or RuleConfig(code=proposal.code, name=proposal.code)
    d = proposal.diff
    new_cfg = RuleConfig(
        code=proposal.code,
        name=d.get("name", base.name),
        enabled=d.get("enabled", base.enabled),
        severity=d.get("severity", base.severity),
        hard_hit=d.get("hard_hit", base.hard_hit),
        version=_bump_version(base.version),
        description=d.get("description", base.description),
        params={**base.params, **(d.get("params") or {})},
    )
    DEFAULT_ENGINE.upsert_rule(new_cfg, persist=True)
    RULE_CHANGES.resolve(change_id, principal.user_id, True, new_cfg.version)
    audit = AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="rule.change_approved",
        target=proposal.code,
        detail={
            "change_id": change_id,
            "new_version": new_cfg.version,
            "proposed_by": proposal.proposed_by,
        },
    )
    return RuleApprovalResult(
        change_id=change_id,
        code=proposal.code,
        status="approved",
        new_version=new_cfg.version,
        audit_id=audit.audit_id,
    )
