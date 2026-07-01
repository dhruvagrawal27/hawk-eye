"""Inference runtime (BACKEND-9, blueprint Part 18.1 / 18.3).

Serves L2 unsupervised + L3 GBDT (+ L4 session when the window is mature) on an assembled feature
vector and returns per-layer scores in 0–1, recording ``model_version`` with every score. Trees in
the hot path (L2/L3 inline); L4 sequence is scored only when ``window_mature``. Registry-driven and
signature-verified via :class:`serving.loader.ModelLoader`; falls back to skipping a layer (never
fabricating a score) if its artifact is missing/unsigned — graceful degradation upstream.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from serving.loader import DEFAULT_LOADER, ModelLoader, SignatureError
from serving.model_state import MODEL_STATE
from serving.stubs.deterministic_models import SCORERS

INLINE_LAYERS = ["L2_unsupervised", "L3_gbdt"]


@dataclass
class ScoreResult:
    scores: dict[str, float] = field(default_factory=dict)
    model_versions: dict[str, str] = field(default_factory=dict)
    degraded_layers: list[str] = field(default_factory=list)


class InferenceRuntime:
    def __init__(self, loader: ModelLoader | None = None):
        self.loader = loader or DEFAULT_LOADER
        self._ready: dict[str, bool] = {}
        self.reload()

    def reload(self) -> None:
        loaded = self.loader.load_all(INLINE_LAYERS + ["L4_sequence"])
        self._ready = dict.fromkeys(loaded, True)

    def ready(self) -> bool:
        return any(self._ready.get(layer) for layer in INLINE_LAYERS)

    def score(
        self,
        feature_vector: dict,
        *,
        layers: list[str] | None = None,
        window_mature: bool = False,
        routing_key: str = "",
    ) -> ScoreResult:
        """Score the requested layers (defaults to inline L2/L3, plus L4 if the window is mature)."""
        wanted = list(layers) if layers else list(INLINE_LAYERS)
        if window_mature and "L4_sequence" not in wanted:
            wanted.append("L4_sequence")

        result = ScoreResult()
        for layer in wanted:
            scorer = SCORERS.get(layer)
            version = self.loader.version_for(layer, routing_key)
            if scorer is None or version is None:
                result.degraded_layers.append(layer)
                continue
            # M2.4 kill-switch: a DISABLED model is skipped (degrades to remaining layers). L1 rules
            # never run here, so an alert always survives even if every ML layer is disabled.
            model_id = self.loader.model_id_for(layer)
            if model_id and MODEL_STATE.is_disabled(model_id):
                result.degraded_layers.append(layer)
                continue
            try:
                result.scores[layer] = float(scorer(feature_vector))
                result.model_versions[layer] = version  # recorded on EVERY score (Part 18.3)
            except Exception:  # never let a single layer take the path down
                result.degraded_layers.append(layer)
        return result


DEFAULT_RUNTIME = InferenceRuntime()
__all__ = ["InferenceRuntime", "ScoreResult", "DEFAULT_RUNTIME", "SignatureError", "INLINE_LAYERS"]
