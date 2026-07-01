"""Registry-driven artifact load + signature verify + canary hot-swap (BACKEND-16, Part 23.4/18.3).

Pulls the Production artifact for a layer from the registry, **verifies its signature**, and loads
it. Rejects unsigned/invalid artifacts (they never serve traffic). Supports a canary hot-swap: a
challenger is loaded alongside and a deterministic per-key canary split routes a percentage of
traffic to it; ``model_version`` is recorded on every score for reproducibility.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from serving.registry import _HIGH_TIERS, REGISTRY, ArtifactMeta, LocalRegistry


class SignatureError(Exception):
    """Raised when an artifact is unsigned or its signature does not verify."""


@dataclass
class LoadedModel:
    layer: str
    model_id: str
    version: str
    meta: ArtifactMeta


@dataclass
class Canary:
    challenger: LoadedModel
    percent: int  # 0..100 of traffic routed to the challenger


class ModelLoader:
    def __init__(self, registry: LocalRegistry | None = None, require_signature: bool = True):
        self.registry = registry or REGISTRY
        self.require_signature = require_signature
        self._loaded: dict[str, LoadedModel] = {}
        self._canaries: dict[str, Canary] = {}

    def _verify(self, meta: ArtifactMeta) -> None:
        if self.require_signature and not meta.signed_valid:
            raise SignatureError(
                f"artifact {meta.model_id}@{meta.version} is unsigned or signature invalid — refusing to load"
            )

    def load_production(self, layer: str) -> LoadedModel | None:
        meta = self.registry.production_for(layer)
        if meta is None:
            return None
        self._verify(meta)
        model = LoadedModel(layer=layer, model_id=meta.model_id, version=meta.version, meta=meta)
        self._loaded[layer] = model
        return model

    def load_production_with_tier_check(
        self, layer: str, *, high_tiers: tuple[str, ...] = _HIGH_TIERS
    ) -> LoadedModel | None:
        """Tier-aware load (M1.4): HIGH/CRITICAL-tier models MUST be validly signed to serve;
        MODERATE/LOW-tier models may load unsigned (dev/demo convenience). This lets a demo run the
        low-risk layers without signing keys while still refusing an unsigned critical scorer."""
        meta = self.registry.production_for(layer)
        if meta is None:
            return None
        if meta.risk_tier in high_tiers:
            self._verify(meta)  # raises SignatureError if unsigned/invalid
        model = LoadedModel(layer=layer, model_id=meta.model_id, version=meta.version, meta=meta)
        self._loaded[layer] = model
        return model

    def load_all(self, layers: list[str]) -> dict[str, LoadedModel]:
        out: dict[str, LoadedModel] = {}
        for layer in layers:
            model = self.load_production(layer)
            if model is not None:
                out[layer] = model
        return out

    def canary_hot_swap(self, model_id: str, version: str, percent: int) -> Canary:
        """Stage a challenger as a canary for its layer (verifies signature first)."""
        meta = self.registry.get(model_id, version)
        if meta is None:
            raise SignatureError(f"unknown artifact {model_id}@{version}")
        self._verify(meta)
        challenger = LoadedModel(layer=meta.layer, model_id=model_id, version=version, meta=meta)
        canary = Canary(challenger=challenger, percent=max(0, min(100, percent)))
        self._canaries[meta.layer] = canary
        return canary

    def version_for(self, layer: str, routing_key: str = "") -> str | None:
        """Return the ``model_version`` that serves ``routing_key`` (honours an active canary)."""
        model = self._loaded.get(layer)
        canary = self._canaries.get(layer)
        if canary and _canary_hit(routing_key, canary.percent):
            return canary.challenger.version
        return model.version if model else None


def _canary_hit(routing_key: str, percent: int) -> bool:
    """Deterministic per-key canary split — same key always routes the same way."""
    if percent <= 0:
        return False
    if percent >= 100:
        return True
    bucket = int(hashlib.sha256(routing_key.encode()).hexdigest(), 16) % 100
    return bucket < percent


DEFAULT_LOADER = ModelLoader()
