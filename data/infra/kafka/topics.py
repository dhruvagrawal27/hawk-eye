"""Kafka topic topology + partition-by-entity policy (DATA-3).

Blueprint Part 8 (event ingestion, l.299) and Part 32.1 (schema governance).
Status: REAL (definitions/policy are pure-python; the live broker is SCAFFOLD —
see clients.py, PLATFORM-1 provisions Kafka on port 9092).

Topics come from data.config.Topics so every DATA module agrees on names:
  events.raw      — normalized L0 events (DATA-5 normalizer, DATA-7 simulator)
  events.signals  — recon/derived signals (DATA-16 SWIFT<->CBS mismatch)
  alerts          — L6 alerts (BACKEND produces; we define the topic)
  audit           — immutable audit trail (DATABASE/BACKEND consume)

Partitioning policy: key every record by the acting ENTITY (employee_id) so that
(a) all events for one entity land on one partition => per-entity ORDERING is
preserved (critical for sequence/velocity features, Part 6.6), and (b) parallelism
scales with entity count. Recon signals key by the linkage correlation id so a
SWIFT<->CBS pair lands together.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from data.config import Topics

PARTITIONING_POLICY = (
    "Partition key = acting entity (employee_id) for events.raw/events.signals so "
    "per-entity ordering is preserved and parallelism scales with entity count. "
    "Recon signals may key by linkage correlation id (swift_ref/cbs_ref) so a "
    "SWIFT<->CBS pair co-locates. alerts/audit key by event_id."
)


@dataclass(frozen=True)
class TopicDef:
    name: str
    partitions: int
    replication: int
    key_field: str          # logical field used to derive the partition key
    description: str
    cleanup_policy: str = "delete"   # "delete" | "compact"
    retention_ms: int = 7 * 24 * 3600 * 1000  # 7d default for raw streams


TOPIC_DEFS: dict[str, TopicDef] = {
    Topics.EVENTS_RAW: TopicDef(
        name=Topics.EVENTS_RAW,
        partitions=12,
        replication=1,            # local Redpanda; >=3 in prod (PLATFORM)
        key_field="actor.employee_id",
        description="Normalized L0 events from the normalizer/simulator.",
    ),
    Topics.EVENTS_SIGNALS: TopicDef(
        name=Topics.EVENTS_SIGNALS,
        partitions=6,
        replication=1,
        key_field="actor.employee_id",
        description="Derived signals (SWIFT<->CBS recon mismatch, DATA-16).",
    ),
    Topics.ALERTS: TopicDef(
        name=Topics.ALERTS,
        partitions=6,
        replication=1,
        key_field="event_id",
        description="L6 alerts (BACKEND produces; DATA defines the topic).",
    ),
    Topics.AUDIT: TopicDef(
        name=Topics.AUDIT,
        partitions=3,
        replication=1,
        key_field="event_id",
        description="Append-only audit trail.",
        cleanup_policy="compact",
        retention_ms=-1,          # keep forever (WORM-friendly; DATABASE owns store)
    ),
}


def all_topics() -> list[str]:
    """Topic names in deterministic order."""
    return sorted(TOPIC_DEFS.keys())


def _dig(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def partition_key(topic: str, msg: dict) -> str:
    """Resolve the partition key for `msg` per the topic's key_field policy."""
    td = TOPIC_DEFS.get(topic)
    field = td.key_field if td else "event_id"
    val = _dig(msg, field)
    if val is None:
        val = msg.get("event_id", "")
    return str(val)


def partition_for(topic: str, msg: dict, partitions: int | None = None) -> int:
    """Deterministic partition index for `msg` (stable hash of the partition key)."""
    td = TOPIC_DEFS.get(topic)
    n = partitions if partitions is not None else (td.partitions if td else 1)
    n = max(1, n)
    key = partition_key(topic, msg)
    h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    return h % n
