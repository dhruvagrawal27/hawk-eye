"""Hash-chaining + daily Merkle anchoring for the WORM audit trail (DATABASE-6).

Tamper-evidence has two layers (blueprint Part 19.3 l.634, Part 8 l.311):

1. **Per-record hash chain.** Each sealed record carries ``prev_hash`` (the prior
   record's ``record_hash``) and ``record_hash = H(content ‖ prev_hash)``. Altering
   any record breaks every subsequent link — the verifier finds the first break.

2. **Daily Merkle anchor.** Every day's record hashes are folded into a binary
   Merkle tree; the **daily root** is the single value a regulator/Internal Audit
   can pin (publish, notarize, print). Re-deriving the root from the sealed
   records must reproduce the pinned value, or the day was tampered with.

Domain-separated hashing (prevents second-preimage / leaf↔node confusion):
    leaf  = SHA-256( 0x00 ‖ record_hash_bytes )
    node  = SHA-256( 0x01 ‖ left ‖ right )
Odd nodes duplicate the last (Bitcoin-style), which is documented and reproduced
identically by the verifier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Mapping, Sequence

from services.audit.audit_schema import compute_record_hash

_LEAF_PREFIX = b"\x00"
_NODE_PREFIX = b"\x01"
# Genesis prev_hash for the very first record in the chain (seq 0).
GENESIS_PREV_HASH = "0" * 64


@dataclass(frozen=True)
class SealedLink:
    """The chaining fields a writer stamps onto a record at seal time."""

    seq: int
    prev_hash: str
    record_hash: str


def seal_link(record: Mapping[str, object], prev_hash: str, seq: int) -> SealedLink:
    """Compute the chaining fields for ``record`` given the running ``prev_hash``."""
    rh = compute_record_hash(record, prev_hash)
    return SealedLink(seq=seq, prev_hash=prev_hash, record_hash=rh)


def _leaf(record_hash_hex: str) -> bytes:
    return hashlib.sha256(_LEAF_PREFIX + bytes.fromhex(record_hash_hex)).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(_NODE_PREFIX + left + right).digest()


def merkle_root(record_hashes: Sequence[str]) -> str:
    """Daily Merkle root over an *ordered* sequence of record hashes (hex)."""
    if not record_hashes:
        # Empty day → well-defined empty root (hash of nothing-leaf marker).
        return hashlib.sha256(_LEAF_PREFIX).hexdigest()
    level: List[bytes] = [_leaf(h) for h in record_hashes]
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplicate last (odd count)
        level = [_node(level[i], level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()


def verify_chain(records: Sequence[Mapping[str, object]]) -> tuple[bool, int, str]:
    """Re-walk an ordered list of sealed records.

    Returns ``(ok, first_bad_index, reason)``. ``ok=True`` ⇒ untouched chain
    (``first_bad_index=-1``). On tamper, ``first_bad_index`` is the 0-based index
    of the **first** divergent record and ``reason`` explains the break.
    """
    expected_prev = GENESIS_PREV_HASH
    for i, rec in enumerate(records):
        prev = str(rec.get("prev_hash", ""))
        if prev != expected_prev:
            return (
                False,
                i,
                f"prev_hash mismatch at seq {i}: stored={prev[:12]}… "
                f"expected={expected_prev[:12]}…",
            )
        recomputed = compute_record_hash(rec, prev)
        stored = str(rec.get("record_hash", ""))
        if recomputed != stored:
            return (
                False,
                i,
                f"record_hash mismatch at seq {i} (audit_id="
                f"{rec.get('audit_id')!r}): content was altered",
            )
        expected_prev = stored
    return (True, -1, "ok")
