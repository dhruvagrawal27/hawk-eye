"""The alert-only contract (ML-9; blueprint Part 1/2 alert-only, Part 16 natural justice, 25.7).

Golden rule #1: models SCORE and EXPLAIN; a human decides. No model output may trigger
an action. This module makes that a *runtime-enforced* contract, not just a doctrine:
a model emits an ``Advisory`` (rank + reasons), never a ``block``/``freeze``/``classify``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Actions a model may emit (advisory only) vs. actions it must NEVER emit (human-only).
ALLOWED_ADVISORY_ACTIONS = ("alert", "rank", "explain", "escalate_for_review", "flag_for_edd")
FORBIDDEN_AUTONOMOUS_ACTIONS = (
    "block", "freeze", "auto_block", "reverse_transaction", "auto_classify_fraud",
    "deny", "suspend_user", "seize", "auto_close",
)


class AlertOnlyViolation(RuntimeError):
    """Raised if model output ever attempts an autonomous (non-advisory) action."""


@dataclass
class Advisory:
    """The only thing a model is allowed to emit: a score + reasons for a human."""

    entity_id: str
    risk_score: float
    reason_codes: list[Any] = field(default_factory=list)
    action: str = "alert"
    narrative: str = ""

    def __post_init__(self) -> None:
        assert_advisory_action(self.action)

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "risk_score": self.risk_score,
            "action": self.action,
            "advisory": True,
            "blocks": False,
            "reason_codes": [getattr(rc, "to_dict", lambda: rc)() for rc in self.reason_codes],
            "narrative": self.narrative,
        }


def assert_advisory_action(action: str) -> None:
    """Raise unless ``action`` is purely advisory (never blocks/decides)."""
    if action in FORBIDDEN_AUTONOMOUS_ACTIONS:
        raise AlertOnlyViolation(
            f"action {action!r} is autonomous/blocking — models are ALERT-ONLY (Part 16). "
            f"A human must decide; allowed advisory actions: {ALLOWED_ADVISORY_ACTIONS}."
        )
    if action not in ALLOWED_ADVISORY_ACTIONS:
        raise AlertOnlyViolation(f"unknown action {action!r}; allowed: {ALLOWED_ADVISORY_ACTIONS}")


def alert_only_contract() -> dict:
    """The machine-readable contract published to other workstreams (CONTEXT.md)."""
    return {
        "principle": "ALERT-ONLY: models score and explain; a human decides.",
        "no_inline_blocking": True,
        "allowed_advisory_actions": list(ALLOWED_ADVISORY_ACTIONS),
        "forbidden_autonomous_actions": list(FORBIDDEN_AUTONOMOUS_ACTIONS),
        "every_alert_is_contestable": "carries reason codes + narrative (Part 29.2)",
        "blueprint": ["Part 1", "Part 2", "Part 16", "Part 25.7"],
    }
