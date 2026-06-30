"""Model inventory (ML-20; blueprint Part 27 MRM).

The model-risk-management inventory: every model in the platform — the L2-L6 scoring
layers AND the LLM narrative gateway — with its owner, purpose, **risk tier**, data,
version, and validation status. Risk tiering follows the blueprint rule that *scoring*
models (which influence whether a person is investigated) outrank the *narrative* LLM
(which only explains, never decides).

This is a pure-Python catalogue (no heavy model imports), so it loads in any process.
The default inventory enumerates exactly the models the blueprint Part 7 + Part 25 name;
:class:`ModelInventory` lets callers add/override entries and reconcile against a live
:class:`ml.mlops.registry.ModelRegistry`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

# Risk tiers, highest impact first. Scoring > narrative LLM (blueprint Part 27).
TIER_CRITICAL = "tier-1-critical"
TIER_HIGH = "tier-2-high"
TIER_MODERATE = "tier-3-moderate"
TIER_LOW = "tier-4-low"
RISK_TIERS = (TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_LOW)

# Validation status lifecycle (Part 27 change->validation->approval->deploy).
VALIDATION_STATUSES = ("not_started", "in_progress", "validated", "approved", "retired")


@dataclass
class InventoryEntry:
    """One model in the MRM inventory (Part 27 attributes)."""

    model_id: str
    layer: str
    owner: str
    purpose: str
    risk_tier: str
    data: str
    version: str = "0.1.0"
    validation_status: str = "not_started"
    decides: bool = (
        True  # True = influences an investigation decision; False = explains only
    )
    review_frequency: str = "quarterly"

    def __post_init__(self) -> None:
        if self.risk_tier not in RISK_TIERS:
            raise ValueError(
                f"risk_tier must be one of {RISK_TIERS}, got {self.risk_tier!r}"
            )
        if self.validation_status not in VALIDATION_STATUSES:
            raise ValueError(
                f"validation_status must be one of {VALIDATION_STATUSES}, got {self.validation_status!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Higher-impact (lower-numbered) tier gets a higher sort weight.
_TIER_RANK = {t: len(RISK_TIERS) - i for i, t in enumerate(RISK_TIERS)}

# The default inventory: every model the blueprint enumerates (Part 7 layers + Part 25 LLM).
# Scoring layers are tiered by how directly they drive an investigation decision; the L6
# fusion meta-model is the most critical (it produces the final 0-100 alert risk score).
_DEFAULT_ENTRIES: tuple[InventoryEntry, ...] = (
    InventoryEntry(
        model_id="l6_fusion",
        layer="L6",
        owner="ml-platform",
        purpose="Stacked meta-model fusing L2-L5 scores + rule flags into the final 0-100 alert risk score.",
        risk_tier=TIER_CRITICAL,
        data="per-layer scores + rule flags (EDD-labelled)",
        review_frequency="monthly",
    ),
    InventoryEntry(
        model_id="l3_supervised",
        layer="L3",
        owner="ml-supervised",
        purpose="Supervised GBDT fraud scorer (LightGBM/CatBoost/XGBoost) over event features.",
        risk_tier=TIER_CRITICAL,
        data="labelled fraud events (time-split, calibrated)",
        review_frequency="monthly",
    ),
    InventoryEntry(
        model_id="l5_graph",
        layer="L5",
        owner="ml-graph",
        purpose="Graph fraud scorer (XGB-Graph default / GraphSAGE) over k-hop entity-graph aggregates.",
        risk_tier=TIER_HIGH,
        data="entity graph (employees/accounts/beneficiaries/devices)",
        review_frequency="quarterly",
    ),
    InventoryEntry(
        model_id="l2_ueba",
        layer="L2",
        owner="ml-unsupervised",
        purpose="Unsupervised UEBA anomaly detection (IsolationForest/ECOD/AE ensemble) on per-entity baselines.",
        risk_tier=TIER_HIGH,
        data="per-entity/per-peer behavioural baselines (unlabelled normal window)",
        review_frequency="quarterly",
    ),
    InventoryEntry(
        model_id="l4_sequence",
        layer="L4",
        owner="ml-sequence",
        purpose="Sequence/session anomaly detection (windowed baselines first; TranAD/USAD if they beat them).",
        risk_tier=TIER_MODERATE,
        data="session/event windows",
        review_frequency="quarterly",
    ),
    InventoryEntry(
        model_id="llm_narrative_gateway",
        layer="LLM",
        owner="ml-narrative",
        purpose="TEE LLM gateway that writes an advisory, AI-generated alert narrative AFTER L6 — explains, never decides.",
        risk_tier=TIER_MODERATE,
        data="tokenized reason codes + alert context (no raw PII)",
        decides=False,  # narrative LLM never drives a decision -> lower tier than scoring
        review_frequency="quarterly",
    ),
)


class ModelInventory:
    """The MRM model inventory: every model with owner/purpose/risk-tier/data/version/status.

    Seeded with the blueprint default (L2-L6 + LLM gateway); callers may ``add``/``update``
    entries and ``reconcile`` versions + validation status against a live registry.
    """

    def __init__(
        self, entries: Optional[list[InventoryEntry]] = None, *, defaults: bool = True
    ) -> None:
        self._entries: dict[str, InventoryEntry] = {}
        if defaults:
            for e in _DEFAULT_ENTRIES:
                # copy so mutating the inventory never mutates the module-level defaults
                self._entries[e.model_id] = InventoryEntry(**asdict(e))
        for e in entries or []:
            self._entries[e.model_id] = e

    def add(self, entry: InventoryEntry) -> InventoryEntry:
        self._entries[entry.model_id] = entry
        return entry

    def get(self, model_id: str) -> Optional[InventoryEntry]:
        return self._entries.get(model_id)

    def update_status(self, model_id: str, status: str) -> InventoryEntry:
        if status not in VALIDATION_STATUSES:
            raise ValueError(
                f"status must be one of {VALIDATION_STATUSES}, got {status!r}"
            )
        e = self._entries[model_id]
        e.validation_status = status
        return e

    def entries(self) -> list[InventoryEntry]:
        """All entries, most-critical risk tier first (then by layer)."""
        return sorted(
            self._entries.values(),
            key=lambda e: (-_TIER_RANK[e.risk_tier], e.layer, e.model_id),
        )

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.entries()]

    @property
    def layers_covered(self) -> set[str]:
        return {e.layer for e in self._entries.values()}

    def covers_all_layers(self) -> bool:
        """True iff the inventory lists L2-L6 scoring layers + the LLM gateway (acceptance)."""
        required = {"L2", "L3", "L4", "L5", "L6", "LLM"}
        return required.issubset(self.layers_covered)

    def by_tier(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {t: [] for t in RISK_TIERS}
        for e in self.entries():
            out[e.risk_tier].append(e.model_id)
        return out

    def reconcile(self, registry: Any) -> list[dict[str, Any]]:
        """Cross-check inventory versions against a live registry; report mismatches.

        For each inventory entry whose ``layer`` has a registered champion, flag a
        version mismatch (the inventory drifted from what's actually deployed).
        """
        out: list[dict[str, Any]] = []
        records = registry.records() if hasattr(registry, "records") else []
        by_layer: dict[str, Any] = {}
        for r in records:
            if getattr(r, "stage", None) == "champion":
                by_layer[r.layer] = r
        for e in self.entries():
            champ = by_layer.get(e.layer)
            if champ is not None and champ.version != e.version:
                out.append(
                    {
                        "model_id": e.model_id,
                        "layer": e.layer,
                        "inventory_version": e.version,
                        "registry_champion_version": champ.version,
                    }
                )
        return out


def default_inventory() -> ModelInventory:
    """The blueprint default MRM inventory (L2-L6 scoring + LLM narrative gateway)."""
    return ModelInventory()


__all__ = [
    "TIER_CRITICAL",
    "TIER_HIGH",
    "TIER_MODERATE",
    "TIER_LOW",
    "RISK_TIERS",
    "VALIDATION_STATUSES",
    "InventoryEntry",
    "ModelInventory",
    "default_inventory",
]
