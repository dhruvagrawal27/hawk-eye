"""Evaluation context for rules (BACKEND-5).

Wraps a canonical L0 event (as a ``dict`` — DATA owns the schema) plus the online feature view
(Feast/Redis keys — DATA materializes; BACKEND reads). Predicates read both. Accessors are
defensive (missing groups → empty dict) so a partial event never raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleContext:
    event: dict
    features: dict = field(default_factory=dict)

    # --- L0 field-group accessors ---
    @property
    def actor(self) -> dict:
        return self.event.get("actor") or {}

    @property
    def action(self) -> dict:
        return self.event.get("action") or {}

    @property
    def obj(self) -> dict:
        return self.event.get("object") or {}

    @property
    def context(self) -> dict:
        return self.event.get("context") or {}

    @property
    def linkage(self) -> dict:
        return self.event.get("linkage") or {}

    # --- common shortcuts ---
    @property
    def event_id(self) -> str:
        return self.event.get("event_id", "")

    @property
    def actor_id(self) -> str:
        return self.actor.get("employee_id", "")

    @property
    def verb(self) -> str:
        return (self.action.get("verb") or "").lower()

    @property
    def channel(self) -> str:
        return (self.action.get("channel") or "").lower()

    @property
    def maker_checker(self) -> str:
        return (self.action.get("maker_checker") or "").lower()

    @property
    def amount(self) -> int:
        amt = self.obj.get("amount")
        return int(amt) if amt is not None else 0

    @property
    def is_off_hours(self) -> bool:
        return bool(self.context.get("is_off_hours") or self.features.get("is_off_hours"))

    def feat(self, key: str, default: Any = None) -> Any:
        """Read an online feature with a default."""
        val = self.features.get(key)
        return default if val is None else val
