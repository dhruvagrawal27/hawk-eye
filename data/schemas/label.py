"""Ground-truth / sourced labels (DATA-10, DATA-23).

Labels are kept SEPARATE from L0 events to prevent leakage (Part 21.4): the event
carries no label field; the simulator emits (event, label) pairs and the label store
joins by event_id / actor_id.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Label:
    event_id: str
    is_fraud: bool = False
    scenario_id: Optional[str] = None     # e.g. "beneficiary_then_approve"
    actor_id: Optional[str] = None        # employee_id of the fraudulent actor
    ring_id: Optional[str] = None         # collusion ring id (RNG-*) when applicable
    lane: Optional[str] = None            # "fast" | "slow" (Part 12)
    label_source: str = "synthetic"       # synthetic | gold | weak | edd
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id, "is_fraud": self.is_fraud, "scenario_id": self.scenario_id,
            "actor_id": self.actor_id, "ring_id": self.ring_id, "lane": self.lane,
            "label_source": self.label_source, "confidence": self.confidence,
        }
