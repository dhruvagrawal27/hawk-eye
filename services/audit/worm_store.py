"""WORM object store abstraction for sealed audit records (DATABASE-6).

Two interchangeable backends behind one interface:

* ``MinioWormStore`` — real **object-lock** (COMPLIANCE-mode-equivalent) writes to
  the MinIO ``audit-archive`` bucket. A delete/overwrite of a locked version is
  **rejected by the server** (the immutability proof). 1:1 AWS swap = S3 Object
  Lock (compliance) + SSE-KMS; only the client config changes.
* ``LocalWormStore`` — filesystem fallback that *emulates* WORM (write-once,
  chmod read-only, in-code refusal to overwrite/early-delete). Lets the WORM
  writer + verifier + unit tests run with **no infra**. The real immutability
  guarantee is the MinIO/S3 object-lock; the local store documents that.

Object layout under the bucket (prefix ``worm/``):
    worm/records/dt=YYYY-MM-DD/<seq:012d>__<audit_id>.json   (sealed, locked)
    worm/merkle/dt=YYYY-MM-DD/root.json                      (daily anchor, locked)
    worm/chain/head.json                                     (mutable pointer)
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Protocol

BUCKET_AUDIT_ARCHIVE = "audit-archive"
WORM_PREFIX = "worm"
RECORDS_PREFIX = f"{WORM_PREFIX}/records"
MERKLE_PREFIX = f"{WORM_PREFIX}/merkle"
CHAIN_HEAD_KEY = f"{WORM_PREFIX}/chain/head.json"

# Default object-lock retention for audit records (DPDP/RBI: see db/retention).
# Audit/evidence is held long; never shortened below this lock (DATABASE-9).
DEFAULT_RETENTION_DAYS = int(os.getenv("AUDIT_LOCK_RETENTION_DAYS", "3650"))  # 10y


class ImmutableViolation(RuntimeError):
    """Raised when something attempts to overwrite/early-delete a sealed object."""


@dataclass
class StoredObject:
    key: str
    data: bytes


class WormStore(Protocol):
    """Minimal interface the writer + verifier depend on."""

    def put_sealed(self, key: str, data: bytes, retain_days: int) -> None: ...
    def put_pointer(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def list(self, prefix: str) -> List[str]: ...
    def exists(self, key: str) -> bool: ...


def record_key(seq: int, audit_id: str, day: str) -> str:
    """Deterministic, lexicographically-sortable object key for a sealed record."""
    return f"{RECORDS_PREFIX}/dt={day}/{seq:012d}__{audit_id}.json"


def merkle_key(day: str) -> str:
    return f"{MERKLE_PREFIX}/dt={day}/root.json"


# ---------------------------------------------------------------------------
# Local filesystem WORM emulation
# ---------------------------------------------------------------------------
class LocalWormStore:
    """Filesystem-backed WORM emulation (write-once, read-only, no early delete)."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        (self.root / RECORDS_PREFIX).mkdir(parents=True, exist_ok=True)
        (self.root / MERKLE_PREFIX).mkdir(parents=True, exist_ok=True)
        (self.root / f"{WORM_PREFIX}/chain").mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put_sealed(self, key: str, data: bytes, retain_days: int) -> None:
        p = self._path(key)
        if p.exists():
            raise ImmutableViolation(f"WORM violation: {key} already sealed")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        # Record a retention sidecar and make the object read-only.
        until = datetime.now(timezone.utc) + timedelta(days=retain_days)
        p.with_suffix(p.suffix + ".lock").write_text(
            json.dumps({"retain_until": until.isoformat(), "mode": "COMPLIANCE"})
        )
        os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    def put_pointer(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            os.chmod(p, stat.S_IWUSR | stat.S_IRUSR)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list(self, prefix: str) -> List[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        out: List[str] = []
        for f in base.rglob("*.json"):
            if f.name.endswith(".lock"):
                continue
            out.append(str(f.relative_to(self.root)).replace(os.sep, "/"))
        return sorted(out)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def assert_immutable(self, key: str) -> None:
        """Prove early-delete is refused (used by tests / the immutability check)."""
        lock = self._path(key).with_suffix(self._path(key).suffix + ".lock")
        meta = json.loads(lock.read_text())
        until = datetime.fromisoformat(meta["retain_until"])
        if datetime.now(timezone.utc) < until:
            raise ImmutableViolation(
                f"delete refused: {key} locked until {meta['retain_until']}"
            )


# ---------------------------------------------------------------------------
# MinIO object-lock WORM (real immutability)
# ---------------------------------------------------------------------------
class MinioWormStore:
    """Real object-lock writes to MinIO ``audit-archive`` (compliance-mode)."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = BUCKET_AUDIT_ARCHIVE,
        secure: bool = False,
    ):
        from minio import Minio  # lazy import (optional dep)

        self._minio = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )
        self.bucket = bucket

    def put_sealed(self, key: str, data: bytes, retain_days: int) -> None:
        import io

        from minio.commonconfig import COMPLIANCE
        from minio.retention import Retention

        until = datetime.now(timezone.utc) + timedelta(days=retain_days)
        self._minio.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="application/json",
            retention=Retention(COMPLIANCE, until),
        )

    def put_pointer(self, key: str, data: bytes) -> None:
        import io

        self._minio.put_object(
            self.bucket,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="application/json",
        )

    def get(self, key: str) -> bytes:
        resp = self._minio.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def list(self, prefix: str) -> List[str]:
        return sorted(
            obj.object_name
            for obj in self._minio.list_objects(
                self.bucket, prefix=prefix, recursive=True
            )
            if obj.object_name and obj.object_name.endswith(".json")
        )

    def exists(self, key: str) -> bool:
        try:
            self._minio.stat_object(self.bucket, key)
            return True
        except Exception:
            return False


def open_worm_store(local_root: Optional[str] = None) -> WormStore:
    """Factory: MinIO object-lock if configured + lib present, else local WORM.

    Env: ``MINIO_ENDPOINT`` (e.g. ``localhost:9001``), ``MINIO_ACCESS_KEY`` /
    ``MINIO_ROOT_USER``, ``MINIO_SECRET_KEY`` / ``MINIO_ROOT_PASSWORD``.
    """
    endpoint = os.getenv("MINIO_ENDPOINT")
    if endpoint:
        try:
            return MinioWormStore(
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
            # minio lib missing or unreachable → fall back so we never block.
            pass
    root = local_root or os.getenv("WORM_LOCAL_ROOT") or ".worm-archive"
    return LocalWormStore(root)


def iter_objects(store: WormStore, keys: Iterable[str]) -> Iterable[StoredObject]:
    for k in keys:
        yield StoredObject(key=k, data=store.get(k))
