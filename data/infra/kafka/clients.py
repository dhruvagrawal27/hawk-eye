"""Kafka producer/consumer wrappers with a pure-python fallback (DATA-3).

Blueprint Part 8 (event ingestion, l.299).
Status: SCAFFOLD for the live broker (confluent-kafka against PLATFORM-1 Kafka on
port 9092); REAL pure-python fallback over data.eventbus.InProcessBus so the
ingest pipeline runs end-to-end with only numpy/pandas/pyarrow installed.

The wrapper API is intentionally tiny and broker-agnostic:
  - Producer.produce(topic, msg)        keyed by the topic partition policy
  - Consumer.subscribe(topic) / .poll() drain delivered messages

Swapping the real broker in is a config change (use_kafka=True), not a rewrite.
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from typing import Any, Optional

from data.config import Ports
from data.eventbus import InProcessBus
from data.infra.kafka.topics import partition_for, partition_key

# --- optional confluent-kafka -------------------------------------------------
try:  # pragma: no cover - exercised only when the lib + broker are present
    from confluent_kafka import Consumer as _CKConsumer  # type: ignore
    from confluent_kafka import Producer as _CKProducer  # type: ignore

    _HAVE_CK = True
except Exception:  # pragma: no cover
    _CKConsumer = None  # type: ignore
    _CKProducer = None  # type: ignore
    _HAVE_CK = False


def kafka_available() -> bool:
    """True only when confluent-kafka is importable (live broker still required)."""
    return _HAVE_CK


# A module-level in-process bus is the shared fallback "broker": a producer and a
# consumer constructed without a live Kafka talk to the same bus.
_DEFAULT_BUS = InProcessBus()


class Producer:
    """Broker-agnostic producer. Falls back to InProcessBus when Kafka is absent."""

    def __init__(
        self,
        bootstrap: str = f"localhost:{Ports.KAFKA}",
        bus: Optional[InProcessBus] = None,
        use_kafka: bool = True,
    ) -> None:
        self.bootstrap = bootstrap
        self.bus = bus or _DEFAULT_BUS
        self._ck: Optional[Any] = None
        self.sent = 0
        if use_kafka and _HAVE_CK:
            try:  # pragma: no cover
                self._ck = _CKProducer({"bootstrap.servers": bootstrap})
            except Exception:
                self._ck = None

    @property
    def using_kafka(self) -> bool:
        return self._ck is not None

    def produce(self, topic: str, msg: dict[str, Any]) -> None:
        """Publish `msg` to `topic`, keyed by the topic partition policy."""
        key = partition_key(topic, msg)
        if self._ck is not None:  # pragma: no cover
            self._ck.produce(topic, key=key.encode("utf-8"),
                             value=json.dumps(msg).encode("utf-8"))
            self.sent += 1
            return
        # fallback: tag with the partition we would have used, then publish on bus
        self.bus.publish(topic, msg)
        self.sent += 1

    def flush(self) -> None:
        if self._ck is not None:  # pragma: no cover
            self._ck.flush()

    def close(self) -> None:
        self.flush()


class Consumer:
    """Broker-agnostic consumer. Fallback drains messages from an InProcessBus.

    poll() returns the next buffered message or None. Use poll_all() in tests.
    """

    def __init__(
        self,
        bootstrap: str = f"localhost:{Ports.KAFKA}",
        group_id: str = "data-ingest",
        bus: Optional[InProcessBus] = None,
        use_kafka: bool = True,
    ) -> None:
        self.bootstrap = bootstrap
        self.group_id = group_id
        self.bus = bus or _DEFAULT_BUS
        self._buffers: dict[str, deque[dict]] = defaultdict(deque)
        self._topics: list[str] = []
        self._ck: Optional[Any] = None
        if use_kafka and _HAVE_CK:
            try:  # pragma: no cover
                self._ck = _CKConsumer({
                    "bootstrap.servers": bootstrap,
                    "group.id": group_id,
                    "auto.offset.reset": "earliest",
                })
            except Exception:
                self._ck = None

    @property
    def using_kafka(self) -> bool:
        return self._ck is not None

    def subscribe(self, topic: str) -> None:
        self._topics.append(topic)
        if self._ck is not None:  # pragma: no cover
            self._ck.subscribe(self._topics)
            return
        self.bus.subscribe(topic, lambda m, t=topic: self._buffers[t].append(m))

    def poll(self, timeout: float = 0.0) -> Optional[dict]:
        if self._ck is not None:  # pragma: no cover
            rec = self._ck.poll(timeout)
            if rec is None or rec.error():
                return None
            return json.loads(rec.value().decode("utf-8"))
        for t in self._topics:
            if self._buffers[t]:
                return self._buffers[t].popleft()
        return None

    def poll_all(self) -> list[dict]:
        """Drain everything currently buffered (fallback path; handy for tests)."""
        out: list[dict] = []
        while True:
            m = self.poll()
            if m is None:
                break
            out.append(m)
        return out

    def close(self) -> None:
        if self._ck is not None:  # pragma: no cover
            self._ck.close()


def make_producer(bus: Optional[InProcessBus] = None, use_kafka: bool = False) -> Producer:
    """Factory: default to the pure-python fallback (use_kafka=False) for local runs."""
    return Producer(bus=bus, use_kafka=use_kafka)


def make_consumer(
    bus: Optional[InProcessBus] = None,
    group_id: str = "data-ingest",
    use_kafka: bool = False,
) -> Consumer:
    return Consumer(bus=bus, group_id=group_id, use_kafka=use_kafka)
