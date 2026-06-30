"""Integration-seam clients (BACKEND consumes; stubbed until each owner is live).

Each client honours the exact BACKEND.md contract so swapping in the real component (DATA feature
store, ML model serving + narrate(), DATABASE registry/WORM) needs no API change. Every stub is
marked ``# STUB: <owner-laptop> <contract>``.
"""

from app.clients.feature_client import FEATURE_READER, FeatureReader
from app.clients.narrative_client import NARRATIVE_CLIENT, NarrativeClient
from app.clients.registry_client import REGISTRY_CLIENT, RegistryClient
from app.clients.serving_client import SERVING_CLIENT, ServingClient

__all__ = [
    "FEATURE_READER", "FeatureReader",
    "SERVING_CLIENT", "ServingClient",
    "NARRATIVE_CLIENT", "NarrativeClient",
    "REGISTRY_CLIENT", "RegistryClient",
]
