"""Hawk-Eye WORM audit subsystem (DATABASE laptop, DATABASE-5/6).

Owns the immutable / WORM audit store, the Kafka audit-topic *consumer* + sealing
sink, per-record hash-chaining + daily Merkle anchoring, and the verification CLI.

BACKEND emits audit events onto the ``hawkeye.audit`` Kafka topic (seam — see
``BACKEND.md`` §3/§7 and CONTEXT.md). This package consumes them and seals them
immutably to the MinIO ``audit-archive`` object-lock bucket. Everyone's actions —
including the investigators' own (who viewed whom, who closed which alert, who
changed a rule/threshold) — are audited (blueprint Part 19.3, "quis custodiet").
"""

from services.audit.audit_schema import (  # noqa: F401
    SCHEMA_VERSION,
    AuditAction,
    TargetType,
    build_envelope,
    canonical_bytes,
    compute_record_hash,
    validate_envelope,
)

__all__ = [
    "SCHEMA_VERSION",
    "AuditAction",
    "TargetType",
    "build_envelope",
    "canonical_bytes",
    "compute_record_hash",
    "validate_envelope",
]
