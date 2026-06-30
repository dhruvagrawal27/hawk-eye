"""Registry access logging (DATABASE-8) — the extraction-theft mitigation.

Blueprint Part 19.2 (l.626): "access logging on the registry". EVERY registry
read / load / promote / register emits an audit event onto the ``hawkeye.audit``
topic (DATABASE-5), which the WORM writer seals immutably (DATABASE-6) — so model
extraction/theft attempts leave a tamper-evident trail.

Emitter backends (auto-selected by env, overridable):
* ``KafkaEmitter``  — produce JSON to ``hawkeye.audit`` (live; optional kafka dep).
* ``WormSealingEmitter`` — seal directly via the WORM writer (self-sealing runtime
  + integration tests that then run ``verify_cli``).
* ``ListEmitter`` — in-memory (pure unit tests).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Protocol

from services.audit.audit_schema import AuditAction, TargetType, build_envelope


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _audit_id() -> str:
    return "aud_" + uuid.uuid4().hex[:12]


class AuditEmitter(Protocol):
    def emit(self, record: Mapping[str, Any]) -> None: ...


class ListEmitter:
    """Collects emitted records in memory (unit tests)."""

    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def emit(self, record: Mapping[str, Any]) -> None:
        self.records.append(dict(record))


class WormSealingEmitter:
    """Seal access-log events straight to WORM (verifiable via verify_cli)."""

    def __init__(self, writer: Optional[Any] = None) -> None:
        if writer is None:
            from services.audit.worm_writer import WormWriter

            writer = WormWriter()
        self._writer = writer

    def emit(self, record: Mapping[str, Any]) -> None:
        self._writer.seal(record)


class KafkaEmitter:  # pragma: no cover - infra path
    """Produce access-log events as JSON onto the audit topic."""

    def __init__(self, bootstrap: str, topic: str = "hawkeye.audit") -> None:
        from confluent_kafka import Producer

        self._p = Producer({"bootstrap.servers": bootstrap})
        self._topic = topic

    def emit(self, record: Mapping[str, Any]) -> None:
        self._p.produce(
            self._topic,
            key=str(record.get("target", {}).get("id", "")),
            value=json.dumps(record).encode("utf-8"),
        )
        self._p.flush(5)


def open_emitter() -> AuditEmitter:
    """Pick an emitter from env: Kafka if bootstrap set, else WORM, else list."""
    bootstrap = os.getenv("KAFKA_BOOTSTRAP")
    if bootstrap and os.getenv("REGISTRY_AUDIT_SINK", "auto") in ("auto", "kafka"):
        try:
            return KafkaEmitter(bootstrap)
        except Exception:
            pass
    if os.getenv("WORM_LOCAL_ROOT") or os.getenv("MINIO_ENDPOINT"):
        try:
            return WormSealingEmitter()
        except Exception:
            pass
    return ListEmitter()


def log_registry_access(
    *,
    action: AuditAction,
    model_ref: str,
    actor: str,
    emitter: AuditEmitter,
    actor_role: str = "service_account",
    details: Optional[Mapping[str, str]] = None,
    ts: Optional[str] = None,
) -> Dict[str, Any]:
    """Build + emit a registry access audit event; return the envelope."""
    record = build_envelope(
        audit_id=_audit_id(),
        ts=ts or _now_iso(),
        actor_id=actor,
        actor_role=actor_role,
        action=action,
        target_type=TargetType.MODEL,
        target_id=model_ref,
        details=dict(details or {}),
    )
    emitter.emit(record)
    return record
