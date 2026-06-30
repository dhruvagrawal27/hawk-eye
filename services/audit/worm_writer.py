"""WORM writer/sink: drain the audit topic → seal immutably (DATABASE-6).

Single-writer design: one consumer of ``hawkeye.audit`` stamps the hash chain and
seals each record to the object-lock ``audit-archive`` bucket. Single-writer ⇒ a
**total order** ⇒ a reproducible chain + daily Merkle root (DATABASE-6 acceptance).

Covers all six WORM record classes (Part 9.3 l.364) + registry access (Part 19.2)
+ investigators' own actions (Part 19.3) — the action enum in ``audit_schema.py``.

Run modes:
* ``WormWriter.seal(record)`` — pure, testable: validate → chain → seal one record.
* ``WormWriter.finalize_day(day)`` — fold the day's records into a Merkle root and
  seal the anchor.
* ``run_kafka(...)`` — long-running consumer loop (optional kafka dep).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

from services.audit.audit_schema import validate_envelope
from services.audit.hashchain import GENESIS_PREV_HASH, merkle_root, seal_link
from services.audit.worm_store import (
    CHAIN_HEAD_KEY,
    DEFAULT_RETENTION_DAYS,
    RECORDS_PREFIX,
    WormStore,
    merkle_key,
    open_worm_store,
    record_key,
)


def _day_of(ts: str) -> str:
    """Extract the UTC day (YYYY-MM-DD) from an ISO-8601 timestamp."""
    return ts[:10]


@dataclass
class ChainHead:
    seq: int
    record_hash: str

    @classmethod
    def genesis(cls) -> "ChainHead":
        return cls(seq=-1, record_hash=GENESIS_PREV_HASH)


class WormWriter:
    """Stateful sealer. Loads the chain head from the store on construction."""

    def __init__(
        self,
        store: Optional[WormStore] = None,
        retain_days: int = DEFAULT_RETENTION_DAYS,
    ):
        self.store = store or open_worm_store()
        self.retain_days = retain_days
        self.head = self._load_head()
        # Per-day accumulator of (seq, record_hash) for Merkle finalization.
        self._day_hashes: Dict[str, List[str]] = {}

    # -- chain head persistence (mutable pointer; corroborated by daily roots) --
    def _load_head(self) -> ChainHead:
        if self.store.exists(CHAIN_HEAD_KEY):
            meta = json.loads(self.store.get(CHAIN_HEAD_KEY))
            return ChainHead(seq=int(meta["seq"]), record_hash=str(meta["record_hash"]))
        return ChainHead.genesis()

    def _save_head(self) -> None:
        self.store.put_pointer(
            CHAIN_HEAD_KEY,
            json.dumps(
                {"seq": self.head.seq, "record_hash": self.head.record_hash}
            ).encode(),
        )

    # -- the core: validate → chain → seal one record --------------------------
    def seal(self, record: Mapping[str, object]) -> Dict[str, object]:
        """Seal one audit record immutably; returns the sealed record."""
        validate_envelope(record)
        seq = self.head.seq + 1
        link = seal_link(record, prev_hash=self.head.record_hash, seq=seq)
        sealed = dict(record)
        sealed["prev_hash"] = link.prev_hash
        sealed["record_hash"] = link.record_hash

        day = _day_of(str(record["ts"]))
        key = record_key(seq, str(record["audit_id"]), day)
        data = json.dumps(sealed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.store.put_sealed(key, data, retain_days=self.retain_days)

        # advance head + accumulate for the day's Merkle tree
        self.head = ChainHead(seq=seq, record_hash=link.record_hash)
        self._save_head()
        self._day_hashes.setdefault(day, []).append(link.record_hash)
        return sealed

    def seal_many(self, records: List[Mapping[str, object]]) -> List[Dict[str, object]]:
        return [self.seal(r) for r in records]

    # -- daily Merkle anchor ---------------------------------------------------
    def finalize_day(self, day: str) -> str:
        """Compute + seal the daily Merkle root anchor. Returns the root hex.

        Reads every record sealed for ``day`` from the store (so it is correct
        across process restarts, not just for in-memory accumulated hashes).
        """
        keys = [k for k in self.store.list(f"{RECORDS_PREFIX}/dt={day}")]
        hashes: List[str] = []
        for k in sorted(keys):
            rec = json.loads(self.store.get(k))
            hashes.append(str(rec["record_hash"]))
        root = merkle_root(hashes)
        anchor = {
            "date": day,
            "count": len(hashes),
            "merkle_root": root,
            "algo": "sha256-domain-separated",
            "chain_head_seq": self.head.seq,
        }
        self.store.put_sealed(
            merkle_key(day),
            json.dumps(anchor, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            retain_days=self.retain_days,
        )
        return root


# ---------------------------------------------------------------------------
# Kafka consumer loop (optional dependency)
# ---------------------------------------------------------------------------
def run_kafka(
    bootstrap: str,
    topic: str = "hawkeye.audit",
    group: str = "worm-writer",
    max_records: Optional[int] = None,
) -> int:
    """Consume the audit topic in order and seal each record. Returns count sealed.

    Decodes JSON values (the local/Redpanda fallback) or Avro-encoded values if a
    schema registry is wired (BACKEND's producer). For the JSON fallback the value
    is a UTF-8 JSON envelope.
    """
    try:
        from confluent_kafka import Consumer  # type: ignore
    except Exception as exc:  # pragma: no cover - infra path
        raise RuntimeError(
            "confluent-kafka not installed; use seal()/seal_many() for tests or "
            "install confluent-kafka for the live consumer loop"
        ) from exc

    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])
    writer = WormWriter()
    sealed = 0
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                if max_records is not None and sealed >= 0:
                    break
                continue
            if msg.error():  # pragma: no cover - infra path
                continue
            record = json.loads(msg.value().decode("utf-8"))
            writer.seal(record)
            consumer.commit(msg)
            sealed += 1
            if max_records is not None and sealed >= max_records:
                break
    finally:
        consumer.close()
    return sealed


def _cli() -> None:  # pragma: no cover - thin wrapper
    ap = argparse.ArgumentParser(description="Hawk-Eye WORM audit writer (DATABASE-6)")
    ap.add_argument(
        "--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:29092")
    )
    ap.add_argument("--topic", default="hawkeye.audit")
    ap.add_argument("--max-records", type=int, default=None)
    ap.add_argument(
        "--finalize-day", default=None, help="YYYY-MM-DD to seal a Merkle root for"
    )
    args = ap.parse_args()
    if args.finalize_day:
        root = WormWriter().finalize_day(args.finalize_day)
        print(f"daily Merkle root {args.finalize_day} = {root}")
        return
    n = run_kafka(args.bootstrap, args.topic, max_records=args.max_records)
    print(f"sealed {n} audit records to WORM")


if __name__ == "__main__":  # pragma: no cover
    _cli()
