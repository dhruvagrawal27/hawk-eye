"""Pytest fixtures for the DATABASE suite.

Forces the infra-free LOCAL backends for unit tests (no MinIO/Kafka/CH/PG needed)
and puts the repo root on sys.path so `services.audit`, `registry.*`, and
`db.retention.*` import cleanly when running `pytest db/tests`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _force_local_backends(monkeypatch, tmp_path):
    """Unit tests use local FS WORM + local artifact store + tmp signing keys."""
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("KAFKA_BOOTSTRAP", raising=False)
    monkeypatch.setenv("WORM_LOCAL_ROOT", str(tmp_path / "worm"))
    monkeypatch.setenv("MODELS_LOCAL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("REGISTRY_KEY_DIR", str(tmp_path / "keys"))
    monkeypatch.setenv(
        "REGISTRY_SIGNING_KEY", str(tmp_path / "keys" / "registry_signing_ed25519.pem")
    )
    monkeypatch.setenv(
        "REGISTRY_PUBLIC_KEY", str(tmp_path / "keys" / "registry_signing_ed25519.pub")
    )
    yield


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: cross-store flow needing live infra (storage compose up); "
        "skips automatically if the store is unreachable.",
    )
