"""Integration fixtures — connect to the live storage compose, skip if absent.

Bring the stack up first:
    docker compose -f infra/storage/docker-compose.storage.yml up -d
Then:
    CH_HOST=localhost MINIO_ENDPOINT=localhost:9001 \
      pytest db/tests/integration -q
Each fixture skips (not fails) when its store is unreachable, so the suite is safe
to run anywhere; CI runs it with the stack up.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def clickhouse_client():
    cc = pytest.importorskip("clickhouse_connect")
    try:
        client = cc.get_client(
            host=os.getenv("CH_HOST", "localhost"),
            port=int(os.getenv("CH_HTTP_PORT", "8123")),
            username=os.getenv("CH_USER", "hawkeye"),
            password=os.getenv("CH_PASSWORD", "hawkeye_dev_pw"),
        )
        client.command("SELECT 1")
    except Exception as exc:  # pragma: no cover - infra dependent
        pytest.skip(f"ClickHouse not reachable: {exc}")
    return client


@pytest.fixture
def minio_client():
    minio = pytest.importorskip("minio")
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9001")
    try:
        client = minio.Minio(
            endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "hawkeye"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw"),
            secure=False,
        )
        list(client.list_buckets())
    except Exception as exc:  # pragma: no cover - infra dependent
        pytest.skip(f"MinIO not reachable: {exc}")
    return client
