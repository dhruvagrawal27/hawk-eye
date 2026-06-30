"""DATABASE-6 — hash-chain + Merkle anchor + WORM seal/verify (infra-free)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from services.audit.audit_schema import AuditAction, TargetType, build_envelope
from services.audit.hashchain import GENESIS_PREV_HASH, merkle_root
from services.audit.verify_cli import verify
from services.audit.worm_store import (
    ImmutableViolation,
    LocalWormStore,
    merkle_key,
)
from services.audit.worm_writer import WormWriter


def _records(n: int, day: str = "2026-06-30"):
    actions = list(AuditAction)
    out = []
    for i in range(n):
        out.append(
            build_envelope(
                audit_id=f"aud_{i:06d}",
                ts=f"{day}T00:{i % 60:02d}:00.000Z",
                actor_id=f"EMP-{i:04d}",
                action=actions[i % len(actions)],
                target_type=TargetType.ALERT,
                target_id=f"alr_{i:06d}",
                details={"i": str(i)},
            )
        )
    return out


def test_merkle_root_deterministic_and_order_sensitive():
    hs = [f"{i:064x}" for i in range(5)]
    assert merkle_root(hs) == merkle_root(hs)
    assert merkle_root(hs) != merkle_root(list(reversed(hs)))


def test_seal_chains_and_verifies_pass(tmp_path):
    store = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=store)
    sealed = w.seal_many(_records(7))
    w.finalize_day("2026-06-30")

    # N records → N sealed objects
    keys = store.list("worm/records")
    assert len(keys) == 7
    # genesis + each prev_hash links to the prior record_hash
    assert sealed[0]["prev_hash"] == GENESIS_PREV_HASH
    for prev, cur in zip(sealed, sealed[1:]):  # noqa: B905 (3.9-compatible)
        assert cur["prev_hash"] == prev["record_hash"]
    # verifier PASS
    passed, report = verify(store)
    assert passed, report


def test_local_store_refuses_overwrite_immutability(tmp_path):
    store = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=store)
    w.seal_many(_records(1))
    key = store.list("worm/records")[0]
    with pytest.raises(ImmutableViolation):
        store.put_sealed(key, b"tamper", retain_days=1)


def test_tampered_copy_fails_with_offending_record(tmp_path):
    # Seal to a real store, then COPY (object-lock objects can't be mutated; the
    # copy is the only way to demonstrate the verifier catches tampering).
    src = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=src)
    w.seal_many(_records(6))
    w.finalize_day("2026-06-30")
    assert verify(src)[0] is True

    copy_root = tmp_path / "copy"
    shutil.copytree(tmp_path / "worm", copy_root)
    copy = LocalWormStore(copy_root)

    # tamper: flip a field in the 3rd sealed record (seq 2)
    keys = sorted(copy.list("worm/records"))
    victim = keys[2]
    rec = json.loads(copy.get(victim))
    rec["details"] = {"i": "TAMPERED"}
    p = Path(copy_root) / victim
    p.chmod(0o644)
    p.write_text(json.dumps(rec, sort_keys=True, separators=(",", ":")))

    passed, report = verify(copy)
    assert passed is False
    joined = "\n".join(report)
    assert "FAIL" in joined
    # the break is detected at or before the tampered record (chain breaks there)
    assert "seq 2" in joined or "0000000002" in joined or "aud_000002" in joined


def test_tail_truncation_detected_via_chain_head(tmp_path):
    # WORM-1: delete the most-recent record BEFORE the day's anchor is sealed.
    src = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=src)
    w.seal_many(_records(5))  # NO finalize_day → open day, no Merkle anchor yet
    assert verify(src)[0] is True

    copy_root = tmp_path / "copy"
    shutil.copytree(tmp_path / "worm", copy_root)
    copy = LocalWormStore(copy_root)
    last = sorted(copy.list("worm/records"))[-1]  # seq 4
    (Path(copy_root) / last).unlink()

    passed, report = verify(copy)
    assert passed is False
    assert any("TAIL-TRUNCATION" in line for line in report), report


def test_same_day_truncation_after_seal_detected(tmp_path):
    # WORM-2: finalize the day, then delete a record + its anchor stays → caught.
    src = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=src)
    w.seal_many(_records(5))
    w.finalize_day("2026-06-30")
    copy_root = tmp_path / "copy"
    shutil.copytree(tmp_path / "worm", copy_root)
    copy = LocalWormStore(copy_root)
    # delete the day's Merkle anchor AND the last record (the WORM-2 exploit)
    (Path(copy_root) / merkle_key("2026-06-30")).unlink()
    (Path(copy_root) / sorted(copy.list("worm/records"))[-1]).unlink()
    passed, report = verify(copy)
    assert passed is False  # caught by chain-head reconciliation despite missing anchor


def test_corrupt_merkle_root_does_not_crash(tmp_path):
    # WORM-3: a null merkle_root must FAIL, not raise TypeError.
    src = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=src)
    w.seal_many(_records(3))
    w.finalize_day("2026-06-30")
    copy_root = tmp_path / "copy"
    shutil.copytree(tmp_path / "worm", copy_root)
    copy = LocalWormStore(copy_root)
    ak = merkle_key("2026-06-30")
    anchor = json.loads(copy.get(ak))
    anchor["merkle_root"] = None
    p = Path(copy_root) / ak
    p.chmod(0o644)
    p.write_text(json.dumps(anchor))
    passed, report = verify(copy)  # must not raise
    assert passed is False
    assert any("MERKLE FAIL" in line for line in report), report


def test_daily_merkle_root_reproducible(tmp_path):
    store = LocalWormStore(tmp_path / "worm")
    w = WormWriter(store=store)
    w.seal_many(_records(4))
    root1 = w.finalize_day("2026-06-30")
    # recompute independently from sealed records
    hashes = [
        json.loads(store.get(k))["record_hash"]
        for k in sorted(store.list("worm/records/dt=2026-06-30"))
    ]
    assert merkle_root(hashes) == root1
