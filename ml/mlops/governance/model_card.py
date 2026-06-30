"""Auto-generated model cards (ML-23; blueprint Part 27).

A per-model model card with every section model-risk requires:

* **intended use** (and out-of-scope use),
* **training data** + its **hash**,
* **features** used,
* **metrics** it was validated on,
* **limitations**,
* **known failure modes**,
* **fairness results** (wired from ``ml.fairness`` via a metrics dict).

The card builds from a :class:`ml.mlops.registry.ModelRecord` (which carries data-hash /
features / metrics / reviewer) plus an :class:`ml.mlops.inventory.InventoryEntry`
(owner / purpose / risk tier). It renders to a JSON-able dict and to Markdown.

Pure-Python (no heavy imports), so it loads in any process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ml.mlops.inventory import InventoryEntry
from ml.mlops.registry import ModelRecord

# Layer -> generic, known failure modes the blueprint calls out (Part 19, 20, 27).
_KNOWN_FAILURE_MODES: dict[str, list[str]] = {
    "L2": [
        "Low-and-slow poisoning of per-entity baselines (mitigated by peer-anchoring + change-point).",
        "Concept drift in 'normal' behaviour inflating false positives until baselines refresh.",
    ],
    "L3": [
        "Label leakage / temporal leakage if features peek into the future (guarded by ml.eval).",
        "Calibration decay under class-prior shift; minority-class recall collapse on rare typologies.",
    ],
    "L4": [
        "Point-adjustment inflation if evaluated naively (forbidden; range/affiliation-aware only).",
        "Deep sequence model failing to beat simple baselines (kept only if it does).",
    ],
    "L5": [
        "Camouflage/heterophily evasion (fraud ring mimicking benign neighbourhoods).",
        "Stale graph snapshots missing newly-formed collusion edges.",
    ],
    "L6": [
        "Mis-calibrated fusion producing over/under-confident 0-100 risk scores.",
        "Over-reliance on a single dominant layer's score, masking disagreement.",
    ],
    "LLM": [
        "Hallucinated facts not grounded in the reason codes (rejected by grounding guard).",
        "Attempted de-anonymisation of tokenized identifiers (forbidden by system prompt).",
    ],
}

_GENERIC_LIMITATIONS = [
    "Trained/validated on synthetic data; real-world performance must be re-validated (synthetic-only guard).",
    "ALERT-ONLY: scores trigger human investigation, never an automated block on a person.",
    "Protected attributes are never used as features; proxy risk is monitored separately.",
]


@dataclass
class ModelCard:
    """A model-risk model card with every required section."""

    model_id: str
    model_version: str
    layer: str
    owner: str
    risk_tier: str
    intended_use: str
    out_of_scope_use: str
    training_data: str
    training_data_hash: Optional[str]
    feature_hash: Optional[str]
    features: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    known_failure_modes: list[str] = field(default_factory=list)
    fairness: dict[str, Any] = field(default_factory=dict)
    approving_reviewer: Optional[str] = None
    validation_status: Optional[str] = None

    REQUIRED_SECTIONS = (
        "intended_use",
        "training_data",
        "training_data_hash",
        "features",
        "metrics",
        "limitations",
        "known_failure_modes",
        "fairness",
    )

    def missing_sections(self) -> list[str]:
        """Required sections that are empty/None (acceptance: a card has ALL sections)."""
        missing: list[str] = []
        for sec in self.REQUIRED_SECTIONS:
            val = getattr(self, sec)
            if val is None or (isinstance(val, (list, dict, str)) and len(val) == 0):
                missing.append(sec)
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_sections()

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "layer": self.layer,
            "owner": self.owner,
            "risk_tier": self.risk_tier,
            "intended_use": self.intended_use,
            "out_of_scope_use": self.out_of_scope_use,
            "training_data": self.training_data,
            "training_data_hash": self.training_data_hash,
            "feature_hash": self.feature_hash,
            "features": list(self.features),
            "metrics": {k: round(float(v), 6) for k, v in self.metrics.items()},
            "limitations": list(self.limitations),
            "known_failure_modes": list(self.known_failure_modes),
            "fairness": self.fairness,
            "approving_reviewer": self.approving_reviewer,
            "validation_status": self.validation_status,
            "is_complete": self.is_complete,
        }

    def to_markdown(self) -> str:
        feats = ", ".join(self.features[:40]) + (
            " ..." if len(self.features) > 40 else ""
        )
        metrics = (
            "\n".join(f"- **{k}**: {v:.4f}" for k, v in self.metrics.items())
            or "- (none)"
        )
        lims = "\n".join(f"- {x}" for x in self.limitations) or "- (none)"
        fails = "\n".join(f"- {x}" for x in self.known_failure_modes) or "- (none)"
        fair = self.fairness or {}
        fair_breach = fair.get("any_breach")
        fair_line = (
            f"- any_breach: **{fair_breach}**; breaches: {fair.get('breaches', {})}"
            if fair
            else "- (not computed)"
        )
        return (
            f"# Model Card — {self.model_id} ({self.model_version})\n\n"
            f"**Layer:** {self.layer}  |  **Owner:** {self.owner}  |  **Risk tier:** {self.risk_tier}  |  "
            f"**Validation status:** {self.validation_status}\n\n"
            f"## Intended use\n{self.intended_use}\n\n"
            f"## Out-of-scope use\n{self.out_of_scope_use}\n\n"
            f"## Training data\n{self.training_data}\n\n"
            f"- **Training-data hash:** `{self.training_data_hash}`\n"
            f"- **Feature-schema hash:** `{self.feature_hash}`\n\n"
            f"## Features\n{feats}\n\n"
            f"## Metrics\n{metrics}\n\n"
            f"## Limitations\n{lims}\n\n"
            f"## Known failure modes\n{fails}\n\n"
            f"## Fairness results\n{fair_line}\n\n"
            f"## Approval\n- Reviewer: {self.approving_reviewer}\n"
        )


def generate_model_card(
    record: ModelRecord,
    entry: InventoryEntry,
    *,
    fairness: Optional[dict[str, Any]] = None,
    extra_limitations: Optional[list[str]] = None,
    extra_failure_modes: Optional[list[str]] = None,
    validation_status: Optional[str] = None,
) -> ModelCard:
    """Auto-generate a complete model card from a registry record + inventory entry.

    ``fairness`` is the dict from ``ml.fairness.fairness_metrics_dict`` (real DI/EO metrics).
    """
    layer = record.layer or entry.layer
    failure_modes = list(_KNOWN_FAILURE_MODES.get(layer, [])) + list(
        extra_failure_modes or []
    )
    if not failure_modes:
        failure_modes = [
            "Generic ML failure modes apply (drift, decay, distribution shift)."
        ]
    limitations = list(_GENERIC_LIMITATIONS) + list(extra_limitations or [])
    out_of_scope = (
        "Not for automated blocking/account-freezing of any individual; not a determination "
        "of guilt; not validated outside the insider-fraud detection scope."
    )
    return ModelCard(
        model_id=entry.model_id,
        model_version=record.model_version,
        layer=layer,
        owner=entry.owner,
        risk_tier=entry.risk_tier,
        intended_use=entry.purpose,
        out_of_scope_use=out_of_scope,
        training_data=entry.data,
        training_data_hash=record.training_data_hash,
        feature_hash=record.feature_hash,
        features=list(record.feature_names),
        metrics=dict(record.metrics),
        limitations=limitations,
        known_failure_modes=failure_modes,
        fairness=fairness or {},
        approving_reviewer=record.approving_reviewer,
        validation_status=validation_status or entry.validation_status,
    )


__all__ = ["ModelCard", "generate_model_card"]
