"""Artifact object store abstraction for the `models` bucket (DATABASE-7/8).

Local filesystem (default, infra-free tests) or MinIO/S3 object-lock backend.
The `models` bucket is encrypted-at-rest + versioned + object-locked + least-
privilege (DATABASE-1). 1:1 AWS swap = S3 with SSE-KMS + Object Lock.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Protocol

BUCKET_MODELS = "models"


class ArtifactStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str) -> List[str]: ...


class LocalArtifactStore:
    """Filesystem-backed model store (root acts as the `models` bucket)."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> None:
        p = self.root / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()

    def list(self, prefix: str) -> List[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(
            str(p.relative_to(self.root)).replace(os.sep, "/")
            for p in base.rglob("*")
            if p.is_file()
        )


class MinioArtifactStore:
    """MinIO/S3-backed model store (object-locked `models` bucket)."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = BUCKET_MODELS,
        secure: bool = False,
    ):
        from minio import Minio  # lazy optional dep

        self._minio = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket = bucket

    def put(self, key: str, data: bytes) -> None:
        import io

        self._minio.put_object(self.bucket, key, io.BytesIO(data), length=len(data))

    def get(self, key: str) -> bytes:
        resp = self._minio.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def exists(self, key: str) -> bool:
        try:
            self._minio.stat_object(self.bucket, key)
            return True
        except Exception:
            return False

    def list(self, prefix: str) -> List[str]:
        return sorted(
            o.object_name
            for o in self._minio.list_objects(
                self.bucket, prefix=prefix, recursive=True
            )
            if o.object_name
        )


def open_artifact_store(local_root: Optional[str] = None) -> ArtifactStore:
    """MinIO if ``MINIO_ENDPOINT`` is set + lib present, else local filesystem."""
    endpoint = os.getenv("MINIO_ENDPOINT")
    if endpoint:
        try:
            return MinioArtifactStore(
                endpoint=endpoint,
                access_key=os.getenv("MINIO_ACCESS_KEY")
                or os.getenv("MINIO_ROOT_USER")
                or "hawkeye",
                secret_key=os.getenv("MINIO_SECRET_KEY")
                or os.getenv("MINIO_ROOT_PASSWORD")
                or "hawkeye_dev_pw",
                secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            )
        except Exception:
            pass
    return LocalArtifactStore(
        local_root or os.getenv("MODELS_LOCAL_ROOT") or ".models-store"
    )
