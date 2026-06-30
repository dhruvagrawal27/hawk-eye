"""Unified ingestion-adapter framework (DATA-15; Part 32.1 pattern, Part 9.1/9.3).

Status: SCAFFOLD. Every concrete adapter reads synthetic *mock fixtures* into the
L0 unified event model now; swapping to a live feed (CBS/SWIFT/IAM/PAM/DB-audit/
IGA/HR) is a config change (point ``source_uri`` at the real feed + supply creds),
not a rewrite. Live feeds need real credentials, hence SCAFFOLD.

This module defines:
  * ``SourceAdapter`` — ABC every connector implements: ``read() -> Iterable[dict]``
    yields raw rows from a fixture; ``to_l0(raw) -> L0Event`` maps one raw row to a
    valid L0 event (passes ``validate_event``); ``stream() -> Iterator[L0Event]``
    glues them together.
  * ``IngestMode`` — CDC-stream (fast lane, low latency) vs periodic-batch (slow lane).
  * ``ReadOnlyCollector`` — the read-only collector concept (Part 9.1/9.3): a
    collector NEVER writes back to the source and NEVER enforces; it only reads
    (ALERT-ONLY golden rule). It carries the source identity + ingest mode and
    drives an adapter.

No external deps beyond the core. Optional Kafka is reached via the core
``KafkaSink`` (guarded there); JSON fixtures are loaded with stdlib ``json``.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Iterator, Optional

from data.schemas import L0Event, validate_event


class IngestMode(str, Enum):
    """CDC→Kafka streaming (fast lane) vs periodic batch (slow lane). Part 32.1."""

    CDC_STREAM = "cdc_stream"      # low-latency change-data-capture -> Kafka
    PERIODIC_BATCH = "periodic_batch"  # periodic export -> slow lane


# Channels the L0 action.channel may carry (kept here so adapters + tests agree).
CHANNELS = {
    "cbs", "swift", "rtgs", "neft", "imps", "upi",
    "iam", "pam", "vpn", "db", "dlp", "hr", "iga", "gl", "treasury",
}


@dataclass
class SourceAdapter(ABC):
    """Base class for every source connector (DATA-13/14/15).

    A concrete adapter:
      1. knows its ``source_name`` (e.g. ``"finacle"``) and ``channel`` (e.g. ``"cbs"``),
      2. ``read()`` yields raw dict rows (from a mock fixture today, a live feed later),
      3. ``to_l0(raw)`` maps ONE raw row to an ``L0Event`` that passes ``validate_event``.

    Read-only: an adapter never mutates the source. Synthetic-only: fixtures carry
    no real PII (EMP-/ACCT-/BEN-/VEN- style ids via the core ``make_id``).
    """

    source_name: str
    channel: str
    mode: IngestMode = IngestMode.CDC_STREAM
    fixture_path: Optional[str] = None
    # collector concept: a source is read-only; we never write back / enforce.
    read_only: bool = True

    # ---- fixture loading -----------------------------------------------------
    def _default_fixture_path(self) -> str:
        """A fixture named ``fixtures.json`` next to the adapter module by default."""
        mod_dir = os.path.dirname(os.path.abspath(self._module_file()))
        return os.path.join(mod_dir, "fixtures.json")

    def _module_file(self) -> str:
        import sys

        mod = sys.modules.get(type(self).__module__)
        f = getattr(mod, "__file__", None)
        return f or __file__

    def load_fixture(self) -> list[dict[str, Any]]:
        """Load the JSON fixture (a list of raw source rows)."""
        path = self.fixture_path or self._default_fixture_path()
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            raise ValueError(f"fixture {path} must be a JSON list of rows")
        return data

    # ---- the two methods every adapter must provide --------------------------
    def read(self) -> Iterable[dict[str, Any]]:
        """Yield raw source rows. Default = the JSON mock fixture.

        SCAFFOLD: a live adapter overrides this to pull from CDC/batch/queue.
        """
        yield from self.load_fixture()

    @abstractmethod
    def to_l0(self, raw: dict[str, Any]) -> L0Event:
        """Map one raw source row to a valid L0 event. Must pass ``validate_event``."""
        raise NotImplementedError

    # ---- glue ----------------------------------------------------------------
    def stream(self) -> Iterator[L0Event]:
        """Read raw rows and yield validated L0 events. Skips nothing; raises on invalid."""
        for raw in self.read():
            ev = self.to_l0(raw)
            errors = validate_event(ev.to_dict())
            if errors:
                raise ValueError(
                    f"{self.source_name}: produced invalid L0 event {ev.event_id}: {errors}"
                )
            if ev.action.channel != self.channel:
                raise ValueError(
                    f"{self.source_name}: channel mismatch "
                    f"{ev.action.channel!r} != {self.channel!r}"
                )
            yield ev

    def collect(self) -> list[L0Event]:
        """Materialize the full stream (convenience for tests / batch lane)."""
        return list(self.stream())


@dataclass
class ReadOnlyCollector:
    """Read-only collector agent (Part 9.1/9.3 / DATA-15).

    Models a read-only tap on a source system: it drives an adapter, never writes
    back, never enforces (ALERT-ONLY). The ``mode`` carries CDC-stream vs batch.
    A real collector would attach to a CDC log / SIEM / message queue; here it just
    iterates the adapter's mock fixture.
    """

    adapter: SourceAdapter
    enforce: bool = False  # ALWAYS False: collectors never block/enforce.

    def __post_init__(self) -> None:
        if self.enforce:
            raise ValueError("collectors are read-only / ALERT-ONLY; enforce must be False")

    @property
    def source_name(self) -> str:
        return self.adapter.source_name

    @property
    def mode(self) -> IngestMode:
        return self.adapter.mode

    def poll(self) -> Iterator[L0Event]:
        """Read-only poll of the source -> validated L0 events."""
        yield from self.adapter.stream()
