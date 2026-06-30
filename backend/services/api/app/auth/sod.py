"""Separation-of-Duties (SoD) enforcement engine (BACKEND-3, blueprint Part 19.6/24.1).

The key SoD rule (Part 19.6): *the person who deploys models cannot label data or close their
own alerts; the person who investigates cannot tune the rules that generate their alerts
unchecked.* This prevents the anti-fraud system from being quietly turned against the bank or an
individual. PII unmask is a separate, audited permission (RBAC). Promotion needs a second-person
sign-off (promoter ≠ approver).

These checks are *in addition to* the RBAC matrix — RBAC says "may this role ever", SoD says "may
this specific actor, on this specific object, right now". Routes call these and convert
``SoDError`` into HTTP 403.
"""

from __future__ import annotations

from app.auth.principal import Principal
from app.schemas.common import Capability, Role


class SoDError(Exception):
    """Raised when a Separation-of-Duties constraint is violated."""

    def __init__(self, rule: str, detail: str):
        self.rule = rule
        self.detail = detail
        super().__init__(f"SoD[{rule}]: {detail}")


# Roles that deploy/train models — they must not also label data or close their own alerts.
_DEPLOYER_ROLES = {Role.MODEL_ENGINEER, Role.PLATFORM_ADMIN}


def check_disposition(
    principal: Principal, alert_owner: str | None, subject_entity: str | None
) -> None:
    """Guard ``POST /alerts/{id}/disposition`` (writing a label / closing an alert).

    * A model deployer cannot label data or close alerts (RBAC already denies disposition for
      Model Engineer; this is defence-in-depth for any future role that has both capabilities).
    * No one may disposition an alert about themselves (self-review), nor one they personally own
      as the deployer.
    """
    if principal.role in _DEPLOYER_ROLES or is_model_deployer(principal):
        raise SoDError(
            "deployer_cannot_label",
            f"{principal.user_id} deploys/trains models and may not write labels or close alerts",
        )
    if subject_entity and principal.user_id == subject_entity:
        raise SoDError("no_self_review", f"{principal.user_id} may not disposition their own case")
    if alert_owner and principal.user_id == alert_owner and principal.role == Role.MODEL_ENGINEER:
        raise SoDError("deployer_cannot_close_own", "deployer may not close their own alert")


def check_rule_tuning(principal: Principal, generated_alerts: set[str]) -> None:
    """An investigator may not unilaterally tune the rules that generate *their* alerts.

    Tuning must go through four-eyes (``check_four_eyes``); an investigator who owns alerts
    produced by a rule cannot self-approve a change to it.
    """
    if principal.role in (Role.ANALYST, Role.SENIOR_INVESTIGATOR):
        overlap = principal.assigned_alerts & generated_alerts
        if overlap:
            raise SoDError(
                "investigator_cannot_tune_own_alert_rules",
                f"{principal.user_id} investigates alerts {sorted(overlap)} from this rule; "
                "rule changes require Compliance + four-eyes",
            )


def check_four_eyes(proposer: str, approver: str) -> None:
    """Four-eyes: the approver of a change must differ from the proposer (Part 31.3)."""
    if proposer == approver:
        raise SoDError("four_eyes", f"approver {approver} must differ from proposer {proposer}")


def check_promotion_signoff(requester: str, signoff_by: str) -> None:
    """Model promotion requires a second-person sign-off (Part 24.1 — promoter ≠ approver)."""
    if not signoff_by:
        raise SoDError(
            "promotion_requires_signoff", "model promotion requires a second-person sign-off"
        )
    if requester == signoff_by:
        raise SoDError(
            "promotion_signoff_distinct", f"sign-off {signoff_by} must differ from {requester}"
        )


def check_maker_checker(maker: str | None, checker: str | None) -> None:
    """Toxic combination: the same actor cannot be both maker and checker."""
    if maker and checker and maker == checker:
        raise SoDError("maker_checker_same_actor", f"{maker} is both maker and checker")


def is_model_deployer(principal: Principal) -> bool:
    """A principal who can train/deploy models is a 'deployer' for SoD purposes."""
    return principal.can(Capability.TRAIN_DEPLOY_MODELS)


def constraints_for(role: Role) -> list[str]:
    """Human-readable SoD constraints for a role (surfaced in /admin/users)."""
    out: list[str] = []
    if role in _DEPLOYER_ROLES:
        out += ["cannot_label_data", "cannot_close_own_alerts"]
    if role in (Role.ANALYST, Role.SENIOR_INVESTIGATOR):
        out += ["cannot_tune_own_alert_rules"]
    out += ["pii_unmask_is_separate_audited"]
    return out
