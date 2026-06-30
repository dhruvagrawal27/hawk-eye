"""Rule primitives (BACKEND-5).

``rules_engine`` is intentionally decoupled from the API app: it operates on plain ``dict`` L0
events + an online-feature ``dict`` so it can run inside the Rust/Python hot path, in batch, or
in tests without importing FastAPI. Severities are plain strings; the app maps them to its enum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class RuleConfig:
    """Hot-reloadable, versioned configuration for one named rule (from YAML)."""

    code: str
    name: str
    enabled: bool = True
    severity: Severity = "medium"
    hard_hit: bool = False  # hard-hit rules feed the L1 short-circuit (BACKEND-11)
    version: str = "1.0.0"
    description: str = ""
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RuleHit:
    """A fired rule — becomes a ``reason_code`` of source=rule on the alert."""

    code: str
    version: str
    severity: Severity
    hard_hit: bool
    detail: str
    score: float = 0.0  # 0..1 rule confidence contribution for fusion

    def to_reason_code(self) -> dict:
        return {"source": "rule", "code": self.code, "detail": self.detail}


# A predicate evaluates a context against a rule's params and returns a hit or None.
# Signature: (ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None
