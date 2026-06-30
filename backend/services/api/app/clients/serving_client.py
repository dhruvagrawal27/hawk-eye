"""Model-serving client (BACKEND-9/10 seam).

Calls the serving tier to score L2/L3 (+L4 if mature). In production the Rust gateway calls the
serving HTTP service on :8001; for local/tests this client scores **in-process** against the same
``serving.runtime`` so the control plane runs without a separate serving process. A ``score_remote``
path is provided for the real HTTP seam (httpx → ``HAWKEYE_SERVING_URL``).
"""

from __future__ import annotations

import httpx

from app.config import settings
from serving.runtime import DEFAULT_RUNTIME, ScoreResult


class ServingClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.serving_url

    def score(
        self,
        feature_vector: dict,
        *,
        layers: list[str] | None = None,
        window_mature: bool = False,
        routing_key: str = "",
    ) -> ScoreResult:
        """In-process scoring (default). Deterministic; never raises on a single bad layer."""
        return DEFAULT_RUNTIME.score(
            feature_vector, layers=layers, window_mature=window_mature, routing_key=routing_key
        )

    def score_remote(
        self,
        feature_vector: dict,
        *,
        layers: list[str] | None = None,
        window_mature: bool = False,
        routing_key: str = "",
        timeout: float = 0.3,
    ) -> ScoreResult:  # pragma: no cover - needs the serving service running
        """Real HTTP seam to the serving service on :8001 (used by the gateway in production)."""
        resp = httpx.post(
            f"{self.base_url}/score",
            json={
                "feature_vector": feature_vector,
                "layers": layers,
                "window_mature": window_mature,
                "routing_key": routing_key,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        return ScoreResult(
            scores=body.get("scores", {}),
            model_versions=body.get("model_versions", {}),
            degraded_layers=body.get("degraded_layers", []),
        )

    def ready(self) -> bool:
        return DEFAULT_RUNTIME.ready()


SERVING_CLIENT = ServingClient()
