"""Model serving tier (BACKEND-9/16): runtime, registry-driven signed loader, canary hot-swap."""

from serving.loader import DEFAULT_LOADER, Canary, ModelLoader, SignatureError
from serving.registry import REGISTRY, ArtifactMeta, LocalRegistry, sign
from serving.runtime import DEFAULT_RUNTIME, INLINE_LAYERS, InferenceRuntime, ScoreResult

__all__ = [
    "DEFAULT_LOADER", "ModelLoader", "Canary", "SignatureError",
    "REGISTRY", "ArtifactMeta", "LocalRegistry", "sign",
    "DEFAULT_RUNTIME", "InferenceRuntime", "ScoreResult", "INLINE_LAYERS",
]
