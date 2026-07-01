"""Object-store seam for model artifacts / audit archives (MinIO / S3).

Guarded like every other external service: when HAWKEYE_MINIO_ENABLED + boto3 is importable + the
endpoint is reachable, put/get/list hit MinIO; otherwise a safe no-op fallback keeps the app working.
Nothing in the alert-only runtime *requires* it — it's the durable home for model binaries and audit
exports on deploy. Surfaced on the Service Map (key 'minio').
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger("hawkeye.artifacts")


class ArtifactStore:
    def __init__(self) -> None:
        self._client = None
        if settings.minio_enabled:
            self._client = self._connect()

    def _connect(self):
        try:
            import boto3  # type: ignore
            from botocore.config import Config  # type: ignore

            client = boto3.client(
                "s3",
                endpoint_url=settings.minio_endpoint,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=Config(connect_timeout=2, retries={"max_attempts": 1}),
            )
            # ensure the bucket exists (idempotent)
            try:
                client.head_bucket(Bucket=settings.minio_bucket)
            except Exception:  # noqa: BLE001
                client.create_bucket(Bucket=settings.minio_bucket)
            log.info("minio artifact store active at %s", settings.minio_endpoint)
            return client
        except Exception as exc:  # noqa: BLE001 - unavailable → no-op fallback, never fatal
            log.warning("minio disabled (%s); artifact store is a no-op", exc)
            return None

    @property
    def is_active(self) -> bool:
        return self._client is not None

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        if self._client is None:
            return False
        try:
            self._client.put_object(
                Bucket=settings.minio_bucket, Key=key, Body=data, ContentType=content_type
            )
            return True
        except Exception:  # noqa: BLE001
            return False

    def get(self, key: str) -> bytes | None:
        if self._client is None:
            return None
        try:
            return self._client.get_object(Bucket=settings.minio_bucket, Key=key)["Body"].read()
        except Exception:  # noqa: BLE001
            return None

    def list(self, prefix: str = "") -> list[dict[str, Any]]:
        if self._client is None:
            return []
        try:
            resp = self._client.list_objects_v2(Bucket=settings.minio_bucket, Prefix=prefix)
            return [{"key": o["Key"], "size": o["Size"]} for o in resp.get("Contents", [])]
        except Exception:  # noqa: BLE001
            return []


ARTIFACTS = ArtifactStore()
