"""Model registry client (BACKEND-16/21 seam).

# STUB: DATABASE (registry layout) + ML (MLflow). Wraps ``serving.registry`` + ``serving.loader``
so the ``/models``, ``/models/{id}/promote``, ``/drift`` and ``/metrics/model`` routes read the
registry and verify signatures without defining the bucket/registry layout themselves.
"""

from __future__ import annotations

import logging

from app.config import settings
from serving.loader import DEFAULT_LOADER, SignatureError
from serving.registry import REGISTRY, ArtifactMeta

log = logging.getLogger("hawkeye.registry")


class RegistryClient:
    def __init__(self) -> None:
        self.registry = REGISTRY
        self.loader = DEFAULT_LOADER
        # In-process registry stays the source of truth; mirror to MLflow when enabled + reachable.
        self._mlflow = self._connect_mlflow() if settings.mlflow_enabled else None

    def _connect_mlflow(self):
        try:
            import mlflow  # type: ignore
            from mlflow.tracking import MlflowClient  # type: ignore

            mlflow.set_tracking_uri(settings.mlflow_uri)
            client = MlflowClient()
            client.search_registered_models(max_results=1)  # reachability probe
            log.info("mlflow registry active at %s", settings.mlflow_uri)
            return client
        except Exception as exc:  # noqa: BLE001 - unavailable → in-process registry only
            log.warning("mlflow disabled (%s); in-process registry is the source of truth", exc)
            return None

    @property
    def is_mlflow_active(self) -> bool:
        return self._mlflow is not None

    def list_models(self) -> list[ArtifactMeta]:
        return self.registry.list()

    def get(self, model_id: str, version: str | None = None) -> ArtifactMeta | None:
        return self.registry.get(model_id, version)

    def promote(self, model_id: str, version: str, to_stage: str, canary_percent: int) -> dict:
        """Verify signature, canary hot-swap, set the registry stage. Raises on unsigned/invalid."""
        meta = self.registry.get(model_id, version)
        if meta is None:
            raise SignatureError(f"unknown model {model_id}@{version}")
        canary = self.loader.canary_hot_swap(
            model_id, version, canary_percent
        )  # verifies signature
        self.registry.set_stage(model_id, version, to_stage)
        if self._mlflow is not None:  # best-effort mirror; never blocks the promotion
            try:
                self._mlflow.transition_model_version_stage(model_id, version, to_stage)
            except Exception:  # noqa: BLE001
                pass
        return {
            "model_id": model_id,
            "version": version,
            "stage": to_stage,
            "canary_percent": canary.percent,
            "signature_verified": meta.signed_valid,
        }

    def drift(self, model_id: str) -> dict:
        """# STUB: ML (Evidently/PSI). Deterministic drift snapshot."""
        meta = self.registry.get(model_id) or (self.registry.list()[0])
        # Derive a stable pseudo-PSI from the version string so values are deterministic.
        psi = (sum(ord(c) for c in meta.version) % 25) / 100.0
        return {
            "model_id": meta.model_id,
            "version": meta.version,
            "data_drift_psi": round(psi, 3),
            "concept_drift": round(psi / 2, 3),
            "drift_crossed": psi >= 0.2,
            "window": "rolling_30d",
        }

    def quality(self, model_id: str) -> dict:
        meta = self.registry.get(model_id) or (self.registry.list()[0])
        return {"model_id": meta.model_id, "version": meta.version, **meta.metrics}


REGISTRY_CLIENT = RegistryClient()
