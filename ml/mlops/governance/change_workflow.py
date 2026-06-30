"""Change -> validation -> approval -> deploy workflow that GATES deployment (ML-23).

Blueprint Part 27: a model change cannot reach Production until it has passed each gate
in order. This is a small explicit state machine:

    CHANGE_REQUESTED -> VALIDATED -> APPROVED -> DEPLOYED   (+ RETIRED)

``can_deploy`` / ``deploy`` REFUSE to advance unless every prior gate is satisfied:
the change is recorded, validation passed, an INDEPENDENT approver (not the change author)
signed off, the model card is complete, and (for tiers that require it) the challenger was
shadow-tested. The whole trail is auditable.

Pure-Python (no heavy imports), so it loads in any process.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Stage(str, Enum):
    CHANGE_REQUESTED = "change_requested"
    VALIDATED = "validated"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    RETIRED = "retired"
    REJECTED = "rejected"


# Forward ordering of the happy path; deploy must walk it in order.
_ORDER = [Stage.CHANGE_REQUESTED, Stage.VALIDATED, Stage.APPROVED, Stage.DEPLOYED]


class DeploymentGateError(RuntimeError):
    """Raised when a deploy is attempted before all gates are satisfied."""


@dataclass
class GateEvent:
    stage: str
    actor: str
    note: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "actor": self.actor, "note": self.note, "ts": self.ts}


@dataclass
class ChangeRequest:
    """One governed model change moving through the deployment gates."""

    change_id: str
    model_id: str
    model_version: str
    author: str
    risk_tier: str
    requires_independent_signoff: bool = True
    requires_shadow: bool = True
    stage: Stage = Stage.CHANGE_REQUESTED
    validation_passed: bool = False
    model_card_complete: bool = False
    shadow_passed: bool = False
    approver: Optional[str] = None
    history: list[GateEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.history:
            self.history.append(GateEvent(stage=Stage.CHANGE_REQUESTED.value, actor=self.author,
                                          note="change requested"))

    # --- gates --------------------------------------------------------- #
    def validate(self, *, passed: bool, model_card_complete: bool, shadow_passed: bool = False,
                 actor: str = "validator", note: str = "") -> "ChangeRequest":
        """Record the (independent) validation outcome. Advances to VALIDATED iff passed."""
        self.validation_passed = passed
        self.model_card_complete = model_card_complete
        self.shadow_passed = shadow_passed
        if passed and model_card_complete and (shadow_passed or not self.requires_shadow):
            self.stage = Stage.VALIDATED
            self.history.append(GateEvent(stage=Stage.VALIDATED.value, actor=actor, note=note or "validation passed"))
        else:
            self.stage = Stage.REJECTED
            self.history.append(GateEvent(stage=Stage.REJECTED.value, actor=actor,
                                          note=note or "validation failed / card incomplete / shadow missing"))
        return self

    def approve(self, *, approver: str, note: str = "") -> "ChangeRequest":
        """Independent approval. Refuses if approver == author (separation of duties)."""
        if self.stage != Stage.VALIDATED:
            raise DeploymentGateError(
                f"cannot approve {self.change_id}: stage is {self.stage.value}, must be 'validated' first"
            )
        if self.requires_independent_signoff and approver == self.author:
            raise DeploymentGateError(
                f"approver {approver!r} is the change author; independent sign-off required for "
                f"tier {self.risk_tier}"
            )
        self.approver = approver
        self.stage = Stage.APPROVED
        self.history.append(GateEvent(stage=Stage.APPROVED.value, actor=approver, note=note or "approved"))
        return self

    # --- deploy gate --------------------------------------------------- #
    def deployment_blockers(self) -> list[str]:
        """Reasons the change cannot deploy yet (empty list = ready)."""
        blockers: list[str] = []
        if not self.validation_passed:
            blockers.append("validation has not passed")
        if not self.model_card_complete:
            blockers.append("model card is incomplete")
        if self.requires_shadow and not self.shadow_passed:
            blockers.append("challenger has not passed shadow evaluation")
        if self.stage != Stage.APPROVED:
            blockers.append(f"not yet approved (stage={self.stage.value})")
        if self.requires_independent_signoff and (not self.approver or self.approver == self.author):
            blockers.append("missing independent approver sign-off")
        return blockers

    def can_deploy(self) -> bool:
        return not self.deployment_blockers()

    def deploy(self, *, actor: str = "deployer", note: str = "") -> "ChangeRequest":
        """Advance to DEPLOYED only if every gate is satisfied; else raise (gate enforced)."""
        blockers = self.deployment_blockers()
        if blockers:
            raise DeploymentGateError(
                f"deployment of {self.model_id}@{self.model_version} BLOCKED: {'; '.join(blockers)}"
            )
        self.stage = Stage.DEPLOYED
        self.history.append(GateEvent(stage=Stage.DEPLOYED.value, actor=actor, note=note or "deployed"))
        return self

    def retire(self, *, actor: str = "owner", note: str = "") -> "ChangeRequest":
        """Governed retirement (Part 27)."""
        self.stage = Stage.RETIRED
        self.history.append(GateEvent(stage=Stage.RETIRED.value, actor=actor, note=note or "retired"))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "author": self.author,
            "risk_tier": self.risk_tier,
            "stage": self.stage.value,
            "validation_passed": self.validation_passed,
            "model_card_complete": self.model_card_complete,
            "shadow_passed": self.shadow_passed,
            "approver": self.approver,
            "can_deploy": self.can_deploy(),
            "deployment_blockers": self.deployment_blockers(),
            "history": [h.to_dict() for h in self.history],
        }


__all__ = ["Stage", "ChangeRequest", "GateEvent", "DeploymentGateError"]
