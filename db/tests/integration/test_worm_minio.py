"""DATABASE-6 integration — seal audit events to MinIO object-lock + verify + immutability.

Requires the storage compose up (MinIO + `audit-archive` object-lock bucket).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _records(n):
    from services.audit.audit_schema import AuditAction, TargetType, build_envelope

    return [
        build_envelope(
            audit_id=f"aud_mio{i:04d}",
            ts=f"2026-06-30T01:{i % 60:02d}:00.000Z",
            actor_id=f"EMP-{i}",
            action=AuditAction.VIEW_ALERT,
            target_type=TargetType.ALERT,
            target_id=f"alr_{i}",
        )
        for i in range(n)
    ]


def test_seal_to_object_lock_and_verify(minio_client, monkeypatch):
    from services.audit.verify_cli import verify
    from services.audit.worm_store import MinioWormStore
    from services.audit.worm_writer import WormWriter

    store = MinioWormStore(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9001"),
        access_key=os.getenv("MINIO_ROOT_USER", "hawkeye"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw"),
    )
    w = WormWriter(store=store, retain_days=1)
    w.seal_many(_records(5))
    w.finalize_day("2026-06-30")
    passed, report = verify(store)
    assert passed, report


def test_object_lock_rejects_delete(minio_client):
    """A sealed audit object cannot be deleted within its retention (immutability)."""
    from services.audit.worm_store import MinioWormStore, record_key

    store = MinioWormStore(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9001"),
        access_key=os.getenv("MINIO_ROOT_USER", "hawkeye"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw"),
    )
    key = record_key(999999, "aud_lock01", "2026-06-30")
    store.put_sealed(key, b'{"x":1}', retain_days=1)
    # attempting to remove the locked object/version must be rejected by MinIO
    with pytest.raises(Exception):
        minio_client.remove_object("audit-archive", key)
