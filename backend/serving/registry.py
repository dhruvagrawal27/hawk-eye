"""Model registry reader + signature verification (BACKEND-16, blueprint Part 23.4 / 18.3).

# STUB: DATABASE (object-store + registry layout) + ML (MLflow tracking + ONNX signing).
DATABASE owns the bucket/registry layout and ML owns packaging/signing — BACKEND only **reads** the
registry and **verifies signatures** before load. This local registry seeds the stub L2/L3/L4
artifacts as Production (validly signed) plus an L3 challenger, so the loader/canary path runs
without ML. Swapping in the real MLflow/object-store registry needs no change above this module.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field

_SIGNING_KEY = os.environ.get("HAWKEYE_REGISTRY_SIGNING_KEY", "local-registry-signing-key").encode()


def sign(model_id: str, version: str) -> str:
    """Deterministic stand-in for ML's ONNX signature (cosign/sigstore in production)."""
    return hmac.new(_SIGNING_KEY, f"{model_id}:{version}".encode(), hashlib.sha256).hexdigest()


# M1.4 — FREE-AI / MRMF risk tiers, mirrored from ml.mlops.inventory (Part 27). `ml` is not on the
# backend import path, so the canonical values are duplicated here (kept in lockstep by a doc note).
TIER_CRITICAL = "tier-1-critical"
TIER_HIGH = "tier-2-high"
TIER_MODERATE = "tier-3-moderate"
TIER_LOW = "tier-4-low"
RISK_TIERS = (TIER_CRITICAL, TIER_HIGH, TIER_MODERATE, TIER_LOW)
# Authoritative layer → risk tier (scoring layers outrank the narrative LLM; L6 fusion + L3 are the
# most critical because they most directly drive whether a person is investigated).
LAYER_RISK_TIER = {
    "L2": TIER_HIGH,
    "L3": TIER_CRITICAL,
    "L4": TIER_MODERATE,
    "L5": TIER_HIGH,
    "L6": TIER_CRITICAL,
}
_HIGH_TIERS = (TIER_CRITICAL, TIER_HIGH)


def normalize_layer(layer: str) -> str:
    """`L3_gbdt` -> `L3` so registry layer strings map onto the canonical tier table."""
    return (layer or "").split("_")[0].upper()


@dataclass
class ArtifactMeta:
    model_id: str
    layer: str
    version: str
    stage: str = "Production"  # Production | Staging | Challenger | Archived
    signature: str = ""
    training_data_hash: str | None = None
    feature_set_version: str | None = None
    approving_reviewer: str | None = None
    metrics: dict = field(default_factory=dict)
    uri: str = ""
    risk_tier: str | None = None  # M1.4: MRMF tier (from LAYER_RISK_TIER), gates promote/load

    @property
    def signed_valid(self) -> bool:
        return bool(self.signature) and hmac.compare_digest(
            self.signature, sign(self.model_id, self.version)
        )


class LocalRegistry:
    def __init__(self) -> None:
        self._artifacts: list[ArtifactMeta] = []
        self._seed()

    def _seed(self) -> None:
        def make(model_id, layer, version, stage, metrics, reviewer="EMP-me01"):
            return ArtifactMeta(
                model_id=model_id,
                layer=layer,
                version=version,
                stage=stage,
                signature=sign(model_id, version),  # validly signed
                training_data_hash="sha256:"
                + hashlib.sha256(f"{model_id}{version}".encode()).hexdigest()[:16],
                feature_set_version="fs-2026.06",
                approving_reviewer=reviewer,
                metrics=metrics,
                uri=f"s3://models/{layer}/{version}/model.onnx",
                risk_tier=LAYER_RISK_TIER.get(normalize_layer(layer)),
            )

        self._artifacts = [
            make(
                "l2_isoforest", "L2_unsupervised", "stub-2026.06.30", "Production", {"pr_auc": 0.71}
            ),
            make(
                "l3_lightgbm",
                "L3_gbdt",
                "stub-2026.06.30",
                "Production",
                {"pr_auc": 0.86, "precision_at_k": 0.62},
            ),
            make("l4_usad", "L4_sequence", "stub-2026.06.30", "Production", {"vus_pr": 0.64}),
            make(
                "l3_catboost",
                "L3_gbdt",
                "challenger-2026.06.30",
                "Challenger",
                {"pr_auc": 0.88, "precision_at_k": 0.64},
            ),
            make(
                "l6_meta", "L6_fusion", "stub-2026.06.30", "Production", {"calibration_error": 0.03}
            ),
        ]

    def list(self) -> list[ArtifactMeta]:
        return list(self._artifacts)

    def get(self, model_id: str, version: str | None = None) -> ArtifactMeta | None:
        for a in self._artifacts:
            if a.model_id == model_id and (version is None or a.version == version):
                return a
        return None

    def production_for(self, layer: str) -> ArtifactMeta | None:
        for a in self._artifacts:
            if a.layer == layer and a.stage == "Production":
                return a
        return None

    def set_stage(self, model_id: str, version: str, stage: str) -> ArtifactMeta | None:
        art = self.get(model_id, version)
        if art:
            # Demote any existing Production in the same layer when promoting.
            if stage == "Production":
                for a in self._artifacts:
                    if a.layer == art.layer and a.stage == "Production":
                        a.stage = "Archived"
            art.stage = stage
        return art

    def set_stage_with_tier_gate(
        self, model_id: str, version: str, stage: str, *, signoff_by: str | None = None
    ) -> tuple[ArtifactMeta | None, list[str]]:
        """Tier-gated promotion (M1.4): a tier-1-critical model may only be promoted to Production
        with an independent sign-off (FREE-AI/MRMF). Returns ``(meta, blockers)``; ``blockers``
        non-empty means the promotion was refused and no state changed. ``set_stage`` is left
        untouched for callers that don't want the gate."""
        art = self.get(model_id, version)
        if art is None:
            return None, [f"unknown artifact {model_id}@{version}"]
        blockers: list[str] = []
        if stage == "Production" and art.risk_tier == TIER_CRITICAL and not signoff_by:
            blockers.append("tier-1-critical promotion requires an independent sign-off (signoff_by)")
        if blockers:
            return None, blockers
        return self.set_stage(model_id, version, stage), []


REGISTRY = LocalRegistry()
