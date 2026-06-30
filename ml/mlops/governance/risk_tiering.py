"""Model risk tiering (ML-23; blueprint Part 27).

Tier a model by its *impact*: a model that drives whether a person is investigated
(scoring: L2-L6, above all the L6 fusion that emits the final risk score) outranks one
that only explains (the narrative LLM). The tier then governs HOW DEEP the validation is
and HOW OFTEN the model is reviewed (higher tier -> deeper + more frequent).

This is pure-Python (no heavy imports), so it loads in any process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ml.mlops.inventory import (
    RISK_TIERS,
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_LOW,
    TIER_MODERATE,
    InventoryEntry,
)

# Per-tier governance: validation depth + review cadence (higher tier -> stricter).
_TIER_POLICY: dict[str, dict[str, Any]] = {
    TIER_CRITICAL: {
        "validation_depth": "full-independent",
        "review_frequency": "monthly",
        "requires_independent_signoff": True,
        "requires_fairness_review": True,
        "requires_shadow_before_promote": True,
    },
    TIER_HIGH: {
        "validation_depth": "independent",
        "review_frequency": "quarterly",
        "requires_independent_signoff": True,
        "requires_fairness_review": True,
        "requires_shadow_before_promote": True,
    },
    TIER_MODERATE: {
        "validation_depth": "standard",
        "review_frequency": "quarterly",
        "requires_independent_signoff": False,
        "requires_fairness_review": True,
        "requires_shadow_before_promote": True,
    },
    TIER_LOW: {
        "validation_depth": "light",
        "review_frequency": "annual",
        "requires_independent_signoff": False,
        "requires_fairness_review": False,
        "requires_shadow_before_promote": False,
    },
}


@dataclass
class RiskTierAssessment:
    """A model's assigned risk tier + the governance policy it implies."""

    model_id: str
    risk_tier: str
    decides: bool
    rationale: str
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "risk_tier": self.risk_tier,
            "decides": self.decides,
            "rationale": self.rationale,
            "policy": self.policy,
        }


def assess_risk_tier(
    *,
    model_id: str,
    layer: str,
    decides: bool,
    blocks_or_final: bool = False,
    influences_investigation: bool = True,
) -> RiskTierAssessment:
    """Assign a risk tier from a model's impact characteristics.

    * A model that produces the FINAL alert risk score (L6 fusion) or otherwise determines
      the headline decision -> CRITICAL.
    * A scoring model that materially influences an investigation decision -> HIGH.
    * A model that only explains / never decides (narrative LLM) -> MODERATE at most.
    """
    if not decides:
        tier = TIER_MODERATE
        rationale = (
            "explains only; never drives an investigation decision (e.g. narrative LLM)"
        )
    elif blocks_or_final or layer == "L6":
        tier = TIER_CRITICAL
        rationale = (
            "produces the final/headline risk score that drives the alert decision"
        )
    elif influences_investigation:
        tier = TIER_HIGH
        rationale = (
            "scoring model that materially influences whether a person is investigated"
        )
    else:
        tier = TIER_MODERATE
        rationale = "secondary scoring signal with limited standalone impact"
    return RiskTierAssessment(
        model_id=model_id,
        risk_tier=tier,
        decides=decides,
        rationale=rationale,
        policy=dict(_TIER_POLICY[tier]),
    )


def tier_policy(risk_tier: str) -> dict[str, Any]:
    """The governance policy (validation depth, review cadence, gates) for a tier."""
    if risk_tier not in RISK_TIERS:
        raise ValueError(f"risk_tier must be one of {RISK_TIERS}, got {risk_tier!r}")
    return dict(_TIER_POLICY[risk_tier])


def assess_entry(entry: InventoryEntry) -> RiskTierAssessment:
    """Assess an existing inventory entry (re-derives the tier policy for it)."""
    return assess_risk_tier(
        model_id=entry.model_id,
        layer=entry.layer,
        decides=entry.decides,
        blocks_or_final=(entry.layer == "L6"),
        influences_investigation=entry.decides,
    )


__all__ = [
    "RiskTierAssessment",
    "assess_risk_tier",
    "assess_entry",
    "tier_policy",
    "TIER_CRITICAL",
    "TIER_HIGH",
    "TIER_MODERATE",
    "TIER_LOW",
]
