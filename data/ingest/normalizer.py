"""Normalization / ingest layer: raw source row -> L0 event (DATA-5).

Blueprint Part 5.1 (l.173): map a raw source row to the canonical L0 event and land
it on Kafka events.raw (hot path) AND a ClickHouse events table (history).

Status: REAL on the pure-python path. The ClickHouse sink is OPTIONAL/guarded
(SCAFFOLD: DDL coordinated with DATABASE-CLICKHOUSE; clickhouse-connect required for
the live sink). With only numpy/pandas/pyarrow installed the normalizer writes to a
JSONL/Parquet history sink + the in-process bus, so the path runs end-to-end.

IDEMPOTENCY (Part 32.2): the event_id is a DETERMINISTIC hash of the source + a set
of STABLE source fields via make_id('event', ...). The same raw row always maps to
the same event_id, so the DATA-17 deduper drops replays.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from data.config import CURRENCY_DEFAULT, is_off_hours, make_id
from data.eventbus import InProcessBus
from data.schemas import (
    Action,
    Actor,
    Context,
    L0Event,
    Linkage,
    ObjectRef,
    validate_event,
)

# Stable fields (per source) used to derive the deterministic, idempotent event_id.
# Chosen to identify "the same real-world action" so a re-delivered row dedupes.
_STABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "cbs": ("cbs_ref", "ts", "employee_id", "verb", "amount"),
    "swift": ("swift_ref", "ts", "employee_id", "verb", "instrument"),
    "iam": ("session_id", "ts", "employee_id", "verb", "src_ip"),
    "pam": ("session_id", "ts", "employee_id", "verb", "host"),
    "hr": ("ts", "employee_id", "verb", "entitlement_id"),
    "dlp": ("ts", "employee_id", "verb", "table"),
    "db": ("db_write_id", "ts", "employee_id", "verb", "table"),
}
_DEFAULT_STABLE = ("ts", "employee_id", "verb")


def _stable_event_id(source: str, raw: dict[str, Any]) -> str:
    fields = _STABLE_FIELDS.get(source, _DEFAULT_STABLE)
    parts = [source] + [str(raw.get(f, "")) for f in fields]
    return make_id("event", *parts)


def _hour_weekday(ts: str) -> tuple[Optional[int], Optional[int]]:
    """Best-effort (hour, weekday) from an ISO-8601 'Z' timestamp for is_off_hours."""
    from datetime import datetime

    try:
        s = ts[:-1] if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(s)
        return dt.hour, dt.weekday()
    except Exception:
        return None, None


def normalize(raw: dict[str, Any], source: str) -> L0Event:
    """Map a raw source row + `source` tag to a valid L0Event (idempotent event_id).

    `raw` is a flat dict of source fields (employee_id, verb, ts, ... plus any of the
    L0 field-group keys). Unknown keys are ignored. is_off_hours is derived from ts
    when not supplied. Currency defaults to INR (CONTEXT.md §6).
    """
    event_id = _stable_event_id(source, raw)
    ts = str(raw.get("ts", ""))

    off = raw.get("is_off_hours")
    if off is None:
        hour, weekday = _hour_weekday(ts)
        off = is_off_hours(hour, weekday) if hour is not None else None

    actor = Actor(
        employee_id=str(raw.get("employee_id", "")),
        role=raw.get("role"),
        dept=raw.get("dept"),
        branch=raw.get("branch"),
        tenure_days=raw.get("tenure_days"),
        manager_id=raw.get("manager_id"),
        peer_group=raw.get("peer_group"),
        privileged_flag=bool(raw.get("privileged_flag", False)),
        leaver_flag=bool(raw.get("leaver_flag", False)),
        notice_period=bool(raw.get("notice_period", False)),
    )
    action = Action(
        verb=str(raw.get("verb", "")),
        channel=raw.get("channel", source),
        maker_checker=raw.get("maker_checker"),
    )
    obj = ObjectRef(
        account_id=raw.get("account_id"),
        beneficiary_id=raw.get("beneficiary_id"),
        table=raw.get("table"),
        entitlement_id=raw.get("entitlement_id"),
        instrument=raw.get("instrument"),
        amount=raw.get("amount"),
        currency=raw.get("currency", CURRENCY_DEFAULT),
    )
    context = Context(
        ts=ts,
        src_ip=raw.get("src_ip"),
        device=raw.get("device"),
        geo=raw.get("geo"),
        session_id=raw.get("session_id"),
        layer=raw.get("layer"),
        is_off_hours=off,
        host=raw.get("host"),
    )
    linkage = Linkage(
        swift_ref=raw.get("swift_ref"),
        cbs_ref=raw.get("cbs_ref"),
        app_txn_id=raw.get("app_txn_id"),
        db_write_id=raw.get("db_write_id"),
        maker_id=raw.get("maker_id"),
        checker_id=raw.get("checker_id"),
        customer_account=raw.get("customer_account"),
    )
    return L0Event(event_id=event_id, ts=ts, actor=actor, action=action,
                   object=obj, context=context, linkage=linkage)


# --- optional ClickHouse history sink (SCAFFOLD) ------------------------------
CLICKHOUSE_EVENTS_DDL = """
-- ClickHouse events history table (DATA-5). DDL coordinated with DATABASE-CLICKHOUSE.
CREATE TABLE IF NOT EXISTS events (
  event_id     String,
  ts           DateTime64(3, 'UTC'),
  employee_id  String,
  verb         String,
  channel      String,
  amount       Nullable(Int64),
  currency     LowCardinality(String),
  is_off_hours Nullable(UInt8),
  swift_ref    Nullable(String),
  cbs_ref      Nullable(String),
  payload      String          -- full L0 JSON for replay/investigation
) ENGINE = MergeTree
ORDER BY (employee_id, ts);
""".strip()


class _ClickHouseSink:  # pragma: no cover - requires clickhouse-connect + live server
    """Optional ClickHouse sink. No-op when the driver/server is absent (SCAFFOLD)."""

    def __init__(self, host: str = "localhost", port: int = 8123) -> None:
        self.client = None
        try:
            import clickhouse_connect  # type: ignore

            self.client = clickhouse_connect.get_client(host=host, port=port)
            self.client.command(CLICKHOUSE_EVENTS_DDL)
        except Exception:
            self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    def write(self, ev: L0Event) -> None:
        if self.client is None:
            return
        import json

        d = ev.to_dict()
        self.client.insert(
            "events",
            [[d["event_id"], d["ts"], d["actor"]["employee_id"], d["action"]["verb"],
              d["action"].get("channel"), d["object"].get("amount"),
              d["object"].get("currency"), d["context"].get("is_off_hours"),
              d["linkage"].get("swift_ref"), d["linkage"].get("cbs_ref"),
              json.dumps(d)]],
        )


@dataclass
class NormalizerSinks:
    """Where a normalized event lands: hot bus (Kafka topic) + history sink.

    - bus + topic: the hot path (InProcessBus locally; Kafka via DATA-3 clients).
    - history: any object with .write(row: dict) (JsonlSink/ParquetSink from
      data.eventbus, or the ClickHouse sink when live).
    """
    bus: Optional[InProcessBus] = None
    topic: str = "events.raw"
    history: Any = None
    clickhouse: bool = False
    _ch_sink: Any = None

    def __post_init__(self) -> None:
        if self.clickhouse and self._ch_sink is None:  # pragma: no cover
            self._ch_sink = _ClickHouseSink()


def ingest(
    raw: dict[str, Any],
    source: str,
    sinks: NormalizerSinks,
    dedupe: Optional[Callable[[str], bool]] = None,
) -> Optional[L0Event]:
    """Normalize + land a raw row. Returns the L0Event, or None if dropped (dup/invalid).

    `dedupe(event_id) -> True if new` plugs in the DATA-17 Deduper for idempotency.
    """
    ev = normalize(raw, source)
    d = ev.to_dict()
    errors = validate_event(d)
    if errors:
        return None
    if dedupe is not None and not dedupe(ev.event_id):
        return None
    if sinks.bus is not None:
        sinks.bus.publish(sinks.topic, d)
    if sinks.history is not None:
        sinks.history.write(d)
    if getattr(sinks, "_ch_sink", None) is not None:  # pragma: no cover
        sinks._ch_sink.write(ev)
    return ev
