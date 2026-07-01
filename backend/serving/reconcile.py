"""Registry ↔ authoritative risk-tier reconciliation (M1.4, FREE-AI / MRMF).

The serving registry is the *runtime* source of truth for which artifact serves each layer. FREE-AI /
draft-MRMF want the served models' risk tiers to match the authoritative model-risk inventory, and
the registry not to silently drift. This reconciler cross-checks each **Production** artifact against
the authoritative layer→tier table (`serving.registry.LAYER_RISK_TIER`) — and, optionally, expected
versions — so drift is caught before an auditor finds it.

Kept in the backend `serving` package (no dependency on `ml.mlops.inventory`, which is not on the
backend import path); the tier values are the same strings the ML inventory uses (Part 27).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from serving.registry import LAYER_RISK_TIER, LocalRegistry, normalize_layer


@dataclass
class RegistryInventoryReport:
    """Outcome of a registry↔authoritative-tier reconcile. ``healthy`` iff every list is empty."""

    tier_missing: list[str] = field(default_factory=list)  # Production artifact with no risk_tier
    tier_mismatch: list[dict] = field(default_factory=list)  # risk_tier != authoritative tier
    version_drift: list[dict] = field(default_factory=list)  # version != expected (when provided)
    untracked: list[str] = field(default_factory=list)  # Production layer absent from the tier table

    @property
    def healthy(self) -> bool:
        return not (self.tier_missing or self.tier_mismatch or self.version_drift or self.untracked)

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "tier_missing": list(self.tier_missing),
            "tier_mismatch": list(self.tier_mismatch),
            "version_drift": list(self.version_drift),
            "untracked": list(self.untracked),
        }


class RegistryInventoryReconciler:
    """Reconcile a serving registry's Production artifacts against the authoritative tier table."""

    def __init__(self, expected_tiers: dict[str, str] | None = None) -> None:
        # normalized-layer -> expected tier; defaults to the canonical table in serving.registry.
        self.expected_tiers = dict(expected_tiers or LAYER_RISK_TIER)

    def reconcile(
        self, registry: LocalRegistry, *, expected_versions: dict[str, str] | None = None
    ) -> RegistryInventoryReport:
        report = RegistryInventoryReport()
        for art in registry.list():
            if art.stage != "Production":
                continue  # only what actually serves traffic
            nl = normalize_layer(art.layer)
            expected_tier = self.expected_tiers.get(nl)
            if expected_tier is None:
                report.untracked.append(art.model_id)
                continue
            if not art.risk_tier:
                report.tier_missing.append(art.model_id)
            elif art.risk_tier != expected_tier:
                report.tier_mismatch.append(
                    {
                        "model_id": art.model_id,
                        "layer": nl,
                        "registry_tier": art.risk_tier,
                        "expected_tier": expected_tier,
                    }
                )
            if expected_versions and nl in expected_versions and expected_versions[nl] != art.version:
                report.version_drift.append(
                    {
                        "model_id": art.model_id,
                        "layer": nl,
                        "registry_version": art.version,
                        "expected_version": expected_versions[nl],
                    }
                )
        return report
