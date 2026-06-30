"""MLflow registry storage/layout config + the register/promote/load facade
(DATABASE-8).

SEAM: ML/PLATFORM run the MLflow *tracking server*; DATABASE owns the **storage
backend + layout + signing + verify-on-load + access logging**. This module ties
them together so a synthetic model can be registered (six-field metadata + signed),
promoted Staging→Production→Archived, and loaded-with-verification — each step
access-logged to the WORM audit trail.

Blueprint Part 23.2 (stages + per-version metadata, l.860-862), Part 23.3
(encrypted/object-lock/least-priv/sign-verified-on-load/lifecycle, l.864-865),
Part 23.4 (serving pulls Production + verifies, l.867-868), Part 19.2 (access log).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from registry.artifacts.serializer import (
    ModelArtifact,
    bundle_files,
    load_chain,
    registry_path,
    save_chain,
)
from registry.artifacts.store import ArtifactStore, open_artifact_store
from registry.mlflow.access_log import AuditEmitter, log_registry_access, open_emitter
from registry.mlflow.load_verify import secure_load
from registry.mlflow.signing import sign_bundle
from services.audit.audit_schema import AuditAction

# MLflow Model Registry stages (Part 23.2).
STAGES = ("Staging", "Production", "Archived")
# The six required per-version metadata fields (Part 23.2). `signature` is filled
# by register(); the caller supplies the other five.
REQUIRED_METADATA = (
    "dataset_hash",
    "params",
    "metrics",
    "training_code_commit",
    "approver",
    "signature",
)


class GovernanceError(RuntimeError):
    """Raised on a metadata/SoD/stage violation."""


@dataclass
class RegistryConfig:
    """Storage/layout config (the MLflow tracking server is ML/PLATFORM)."""

    artifact_root: str = os.getenv("MODEL_REGISTRY_ROOT", "s3://models")
    tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    registry_uri: str = os.getenv("MLFLOW_REGISTRY_URI", "http://mlflow:5000")

    def artifact_uri(self, layer: str, model: str, version: str) -> str:
        return f"{self.artifact_root}/{registry_path(layer, model, version)}/"


def configure_mlflow(cfg: Optional[RegistryConfig] = None) -> RegistryConfig:
    """Wire env so an MLflow client (ML's) uses OUR object store + layout.

    Sets the artifact location + tracking/registry URIs. The actual MLflow server
    runtime is ML/PLATFORM; this only publishes the storage/layout contract.
    """
    cfg = cfg or RegistryConfig()
    os.environ.setdefault("MLFLOW_TRACKING_URI", cfg.tracking_uri)
    os.environ.setdefault("MLFLOW_REGISTRY_URI", cfg.registry_uri)
    # MinIO/S3 artifact store for MLflow (1:1 swap to AWS S3 by changing endpoint).
    os.environ.setdefault(
        "MLFLOW_S3_ENDPOINT_URL", os.getenv("MINIO_S3_URL", "http://minio:9001")
    )
    os.environ.setdefault("AWS_ACCESS_KEY_ID", os.getenv("MINIO_ROOT_USER", "hawkeye"))
    os.environ.setdefault(
        "AWS_SECRET_ACCESS_KEY", os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw")
    )
    return cfg


class Registry:
    """The signed, access-logged model registry facade (DATABASE-8)."""

    def __init__(
        self,
        store: Optional[ArtifactStore] = None,
        emitter: Optional[AuditEmitter] = None,
        config: Optional[RegistryConfig] = None,
    ):
        self.store = store or open_artifact_store()
        self.emitter = emitter or open_emitter()
        self.config = config or RegistryConfig()

    # -- register: write a signed version with six-field metadata -------------
    def register(
        self,
        artifact: ModelArtifact,
        *,
        dataset_hash: str,
        params: Mapping[str, Any],
        metrics: Mapping[str, Any],
        training_code_commit: str,
        approver: str,
        feature_set_version: str = "",
        stage: str = "Staging",
        actor: str = "svc-ml-packager",
    ) -> str:
        """Sign + write the artifact; record the six-field metadata; access-log."""
        if stage not in STAGES:
            raise GovernanceError(f"stage must be one of {STAGES}: {stage!r}")

        # Assemble the six-field metadata. The `signature` field is a STABLE
        # pointer to the detached signature.sig (the authoritative artifact),
        # NOT the signature bytes — embedding the bytes would be self-referential
        # (the signed bundle includes metadata.json, so the digest would change
        # every time we wrote the bytes back). Setting a constant pointer keeps
        # metadata.json byte-stable, so what we sign == what we store == what we
        # verify on load. Reproducibility detail: the detached signature covers
        # this exact metadata.json (incl. dataset_hash/params/metrics/commit/approver).
        artifact.metadata.update(
            {
                "layer": artifact.layer,
                "model": artifact.model,
                "version": artifact.version,
                "dataset_hash": dataset_hash,
                "params": dict(params),
                "metrics": dict(metrics),
                "training_code_commit": training_code_commit,
                "approver": approver,
                "feature_set_version": feature_set_version,
                "stage": stage,
                "signature": "ed25519:detached:signature.sig",
                "signature_algo": "ed25519",
            }
        )
        self._require_metadata(artifact.metadata)
        # Sign the now byte-stable bundle (metadata.json included) ONCE.
        artifact.signature = sign_bundle(bundle_files(artifact))
        ref = save_chain(self.store, artifact)
        log_registry_access(
            action=AuditAction.MODEL_VERSION_REGISTER,
            model_ref=ref,
            actor=actor,
            emitter=self.emitter,
            details={
                "stage": stage,
                "dataset_hash": dataset_hash,
                "approver": approver,
                "training_code_commit": training_code_commit,
            },
        )
        return ref

    # -- promote: record a stage transition (does NOT mutate locked artifact) -
    def promote(
        self,
        layer: str,
        model: str,
        version: str,
        to_stage: str,
        *,
        promoter: str,
        approver: str,
        actor: str = "svc-ml-packager",
    ) -> Dict[str, Any]:
        """Record a Staging→Production→Archived transition with four-eyes/SoD.

        The artifact is object-locked + immutable; the live stage is registry
        state (MLflow + this audit record + Postgres `approvals`), not a rewrite.
        SoD (Part 19.6): promoter != approver.
        """
        if to_stage not in STAGES:
            raise GovernanceError(f"stage must be one of {STAGES}: {to_stage!r}")
        if promoter == approver:
            raise GovernanceError("SoD violation: promoter must differ from approver")
        ref = registry_path(layer, model, version)
        record = log_registry_access(
            action=AuditAction.MODEL_VERSION_PROMOTE,
            model_ref=ref,
            actor=actor,
            emitter=self.emitter,
            details={"to_stage": to_stage, "promoter": promoter, "approver": approver},
        )
        return {"model_ref": ref, "stage": to_stage, "audit_id": record["audit_id"]}

    # -- load: signature-verified + access-logged -----------------------------
    def load(
        self, layer: str, model: str, version: str, *, actor: str = "svc-serving-loader"
    ) -> ModelArtifact:
        return secure_load(
            layer, model, version, actor=actor, store=self.store, emitter=self.emitter
        )

    # -- read metadata (access-logged READ; for governance views) -------------
    def read_metadata(
        self, layer: str, model: str, version: str, *, actor: str = "svc-auditor"
    ) -> Dict[str, Any]:
        art = load_chain(self.store, layer, model, version)
        log_registry_access(
            action=AuditAction.REGISTRY_READ,
            model_ref=art.ref,
            actor=actor,
            emitter=self.emitter,
            details={"stage": str(art.metadata.get("stage", ""))},
        )
        return art.metadata

    @staticmethod
    def _require_metadata(metadata: Mapping[str, Any]) -> None:
        missing: List[str] = [f for f in REQUIRED_METADATA if not metadata.get(f)]
        if missing:
            raise GovernanceError(f"metadata.json missing required fields: {missing}")
