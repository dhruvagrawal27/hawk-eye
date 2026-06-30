"""WORM audit verification CLI (DATABASE-6).

Re-reads the sealed objects, re-walks the hash chain, recomputes each daily Merkle
root, and reports **PASS** on an untouched chain or **FAIL** with the first
divergent record on tamper. This is the tool a regulator / Internal Audit runs to
prove the trail was not altered.

    python -m services.audit.verify_cli                 # verify the live WORM store
    python -m services.audit.verify_cli --local ./copy  # verify a (mutable) COPY

Testing immutability: you cannot mutate a real object-lock object, so the tamper
test copies the archive, flips a byte in one record, and points ``--local`` at the
copy — the CLI then returns FAIL at exactly that record (the copy proves the
verifier catches tampering; the real object proves it *can't be* tampered).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Mapping, Optional, Tuple

from services.audit.hashchain import merkle_root, verify_chain
from services.audit.worm_store import (
    CHAIN_HEAD_KEY,
    RECORDS_PREFIX,
    LocalWormStore,
    WormStore,
    merkle_key,
    open_worm_store,
)


def _load_ordered(store: WormStore) -> List[Tuple[int, str, Mapping[str, object]]]:
    """All sealed records as ``(seq, key, record)``, ordered by the seq in the key."""
    keys = store.list(RECORDS_PREFIX)

    # Keys are worm/records/dt=.../<seq:012d>__<audit_id>.json → sort by seq.
    def seq_of(k: str) -> int:
        return int(k.rsplit("/", 1)[-1].split("__", 1)[0])

    pairs = [(seq_of(k), k, json.loads(store.get(k))) for k in keys]
    pairs.sort(key=lambda t: t[0])
    return pairs


def _record_days(pairs: List[Tuple[int, str, Mapping[str, object]]]) -> List[str]:
    """Days that actually contain sealed RECORDS (not just days that have an anchor).

    Deriving from records (WORM-2 fix) means deleting a day's anchor cannot quietly
    drop that day from verification — the day is still checked.
    """
    days = set()
    for _, k, _ in pairs:
        for part in k.split("/"):
            if part.startswith("dt="):
                days.add(part[3:])
    return sorted(days)


def verify(store: WormStore) -> Tuple[bool, List[str]]:
    """Return ``(passed, report_lines)``. PASS only on an untouched chain."""
    report: List[str] = []
    pairs = _load_ordered(store)
    records: List[Mapping[str, object]] = [r for _, _, r in pairs]
    report.append(f"records sealed: {len(records)}")

    # (1) seq contiguity: seqs must be exactly 0..N-1 → catches a MIDDLE deletion
    #     (a gap) or an inserted/renumbered record before the chain walk.
    for i, (seq, _, rec) in enumerate(pairs):
        if seq != i:
            report.append(
                f"SEQ FAIL: expected seq {i}, found {seq} "
                f"(audit_id={rec.get('audit_id')!r}) — record missing or renumbered"
            )
            return False, report

    # (2) hash chain: every prev_hash links + every record_hash recomputes.
    ok, bad_idx, reason = verify_chain(records)
    if not ok:
        bad = records[bad_idx] if 0 <= bad_idx < len(records) else {}
        report.append(f"CHAIN FAIL @ seq {bad_idx}: {reason}")
        report.append(f"  offending audit_id: {bad.get('audit_id')!r}")
        return False, report
    report.append("chain: PASS (every prev_hash links; every record_hash recomputes)")

    # (3) chain-head reconciliation (WORM-1 fix): the persisted, monotonic head is
    #     the AUTHORITATIVE chain length, so TAIL-TRUNCATION (deleting the most
    #     recent record(s)) is caught even before that day's Merkle anchor is
    #     sealed. (A mutable head can itself be rewritten by an attacker who also
    #     re-chains — the regulator-pinned daily Merkle root is the final anchor.)
    if store.exists(CHAIN_HEAD_KEY):
        head = json.loads(store.get(CHAIN_HEAD_KEY))
        head_seq = int(head.get("seq", -1))
        if head_seq != len(records) - 1:
            report.append(
                f"TAIL-TRUNCATION FAIL: chain head seq={head_seq} but "
                f"{len(records)} records present (expected {head_seq + 1})"
            )
            return False, report
        if records and str(records[-1].get("record_hash")) != str(
            head.get("record_hash")
        ):
            report.append(
                "HEAD FAIL: head.record_hash != the last sealed record's hash"
            )
            return False, report
        report.append(
            f"chain head: PASS (length {len(records)} matches head seq {head_seq})"
        )
    else:
        report.append(
            "chain head: (no head pointer — length not independently anchored)"
        )

    # (4) daily Merkle anchors must reproduce; days derived from RECORDS.
    all_ok = True
    for day in _record_days(pairs):
        if not store.exists(merkle_key(day)):
            report.append(f"merkle {day}: (open day — not yet finalized, no anchor)")
            continue
        anchor = json.loads(store.get(merkle_key(day)))
        day_hashes = [
            str(json.loads(store.get(k))["record_hash"])
            for k in sorted(store.list(f"{RECORDS_PREFIX}/dt={day}"))
        ]
        recomputed = merkle_root(day_hashes)
        stored_root = anchor.get("merkle_root")
        if not isinstance(stored_root, str) or stored_root != recomputed:
            all_ok = False
            shown = (
                stored_root[:16] + "…"
                if isinstance(stored_root, str)
                else repr(stored_root)
            )
            report.append(
                f"MERKLE FAIL {day}: stored={shown} recomputed={recomputed[:16]}…"
            )
            continue
        # same-day truncation AFTER sealing: anchor count must match record count.
        if int(anchor.get("count", -1)) != len(day_hashes):
            all_ok = False
            report.append(
                f"MERKLE COUNT FAIL {day}: anchor count={anchor.get('count')} "
                f"but {len(day_hashes)} records present"
            )
            continue
        report.append(
            f"merkle {day}: PASS ({len(day_hashes)} records, root={recomputed[:16]}…)"
        )
    return all_ok, report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Hawk-Eye WORM audit verifier (DATABASE-6)"
    )
    ap.add_argument(
        "--local",
        default=None,
        help="Verify a local WORM dir (or a mutated COPY) instead of the live store.",
    )
    args = ap.parse_args(argv)

    store: WormStore = LocalWormStore(args.local) if args.local else open_worm_store()
    passed, report = verify(store)
    for line in report:
        print(line)
    verdict = "PASS" if passed else "FAIL"
    print(f"\n=== WORM VERIFY: {verdict} ===")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
