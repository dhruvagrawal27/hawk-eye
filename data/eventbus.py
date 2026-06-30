"""In-process event bus + pluggable sinks (DATA-3/DATA-5 local fallback).

So the simulator and normalizer run end-to-end with NO Kafka/ClickHouse needed.
A real KafkaSink / ClickHouseSink swap in when PLATFORM/DATABASE land (config change,
not a rewrite). JSONL is the zero-dependency default; Parquet uses pyarrow (present).
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Callable, Optional


class InProcessBus:
    """Minimal pub/sub used as a local stand-in for Kafka topics."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

    def subscribe(self, topic: str, fn: Callable[[dict], None]) -> None:
        self._subs[topic].append(fn)

    def publish(self, topic: str, msg: dict) -> None:
        for fn in self._subs.get(topic, []):
            fn(msg)


class JsonlSink:
    """Append-only JSONL sink (stdlib only)."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._fh = open(path, "w", encoding="utf-8")
        self.count = 0

    def write(self, row: dict[str, Any]) -> None:
        self._fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.count += 1

    def close(self) -> None:
        self._fh.flush()
        self._fh.close()

    def __enter__(self) -> "JsonlSink":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class ParquetSink:
    """Buffered Parquet sink (pyarrow). Flattens nested L0 dicts to columns on flush."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self._rows: list[dict[str, Any]] = []
        self.count = 0

    @staticmethod
    def _flatten(row: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in row.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                out.update(ParquetSink._flatten(v, f"{key}."))
            else:
                out[key] = v
        return out

    def write(self, row: dict[str, Any]) -> None:
        self._rows.append(self._flatten(row))
        self.count += 1

    def close(self) -> None:
        import pandas as pd  # available
        df = pd.DataFrame(self._rows)
        df.to_parquet(self.path, index=False)

    def __enter__(self) -> "ParquetSink":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class KafkaSink:
    """Optional Kafka producer (confluent-kafka). Falls back to a no-op warning if absent.

    Goes live when PLATFORM-1 provisions Kafka (port 9092). SCAFFOLD-friendly.
    """

    def __init__(self, topic: str, bootstrap: str = "localhost:9092") -> None:
        self.topic = topic
        self._producer: Optional[Any] = None
        try:
            from confluent_kafka import Producer  # type: ignore
            self._producer = Producer({"bootstrap.servers": bootstrap})
        except Exception:
            self._producer = None  # not installed / not running -> local fallback

    @property
    def available(self) -> bool:
        return self._producer is not None

    def write(self, row: dict[str, Any]) -> None:
        if self._producer is None:
            return
        self._producer.produce(self.topic, json.dumps(row).encode("utf-8"))

    def close(self) -> None:
        if self._producer is not None:
            self._producer.flush()
