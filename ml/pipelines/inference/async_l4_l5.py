"""Async lane: L4/L5 UPGRADE an existing alert, never block (ML-18; blueprint Part 18).

Deep / graph models run OFF the hot path (on session-close or batch cadence). They cannot
create latency on the live request and they never block; their only effect is to UPGRADE an
already-emitted fast-lane alert — raising its risk_score / adding reason codes / extending
contributing_layers when they find extra signal. An async pass NEVER lowers an alert below
its fast-lane floor and NEVER blocks a transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from ml.base.interfaces import ReasonCode, severity_from_score


@dataclass
class AlertUpgrade:
    entity_id: str
    old_risk_score: int
    new_risk_score: int
    added_layers: list[str] = field(default_factory=list)
    added_reason_codes: list[ReasonCode] = field(default_factory=list)
    blocked: bool = False  # ALWAYS False — async never blocks.

    @property
    def upgraded(self) -> bool:
        return self.new_risk_score > self.old_risk_score or bool(self.added_layers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "old_risk_score": self.old_risk_score,
            "new_risk_score": self.new_risk_score,
            "added_layers": self.added_layers,
            "added_reason_codes": [rc.to_dict() for rc in self.added_reason_codes],
            "upgraded": self.upgraded,
            "blocked": self.blocked,
        }


class AsyncUpgrader:
    """Apply an async L4/L5 score to an existing alert dict, upgrading (never lowering)."""

    def __init__(self, *, layer: str, model_version: str = "unknown") -> None:
        self.layer = layer.upper()
        self.model_version = model_version

    def upgrade(
        self,
        existing_alert: dict[str, Any],
        *,
        async_score: float,
        reason_codes: Optional[list[ReasonCode]] = None,
    ) -> AlertUpgrade:
        """Upgrade ``existing_alert`` IN PLACE with an async [0,1] score. Never blocks."""
        old = int(existing_alert.get("risk_score", 0))
        async_100 = int(round(float(np.clip(async_score, 0.0, 1.0)) * 100))
        # UPGRADE-ONLY: take the max so we never lower a fast-lane alert.
        new = max(old, async_100)

        added_layers: list[str] = []
        layer_label = {"L4": "L4_sequence", "L5": "L5_graph"}.get(
            self.layer, self.layer
        )
        contributing = list(existing_alert.get("contributing_layers", []))
        if new > old and layer_label not in contributing:
            contributing.append(layer_label)
            added_layers.append(layer_label)

        rcs = reason_codes or []
        # write back (mutating the existing alert — this is an upgrade, not a new alert)
        existing_alert["risk_score"] = new
        existing_alert["severity"] = severity_from_score(new).value
        existing_alert["contributing_layers"] = contributing
        existing_alert.setdefault("reason_codes", [])
        existing_alert["reason_codes"].extend(rc.to_dict() for rc in rcs)
        existing_alert["status"] = existing_alert.get(
            "status", "open"
        )  # never auto-close/block

        return AlertUpgrade(
            entity_id=str(existing_alert.get("entity_id", "")),
            old_risk_score=old,
            new_risk_score=new,
            added_layers=added_layers,
            added_reason_codes=rcs,
            blocked=False,
        )


def run_async_upgrade(
    existing_alert: dict[str, Any],
    scorer: Any,
    X,
    *,
    layer: str,
    reason_codes: Optional[list[ReasonCode]] = None,
) -> AlertUpgrade:
    """Score ``X`` with an async scorer and upgrade ``existing_alert`` (never block)."""
    if hasattr(scorer, "predict_proba"):
        s = float(np.asarray(scorer.predict_proba(X)).ravel()[0])
    else:
        s = float(np.asarray(scorer.score_samples(X)).ravel()[0])
    up = AsyncUpgrader(
        layer=layer, model_version=getattr(scorer, "model_version", "unknown")
    )
    return up.upgrade(existing_alert, async_score=s, reason_codes=reason_codes)


__all__ = ["AsyncUpgrader", "AlertUpgrade", "run_async_upgrade"]
