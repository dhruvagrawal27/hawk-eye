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


REGISTRY = LocalRegistry()
