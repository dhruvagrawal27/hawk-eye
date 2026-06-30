"""Purpose-bound retention, lifecycle deletion & erasure with carve-outs (DATA-27).

Blueprint Part 28.1 (l.1197): "data minimization, purpose limitation, retention &
erasure — define purpose-bound retention timelines; automate lifecycle deletion; honour
erasure with carve-outs for legal/fraud-investigation obligations." Part 28.2 retention
& archival (l.1208). Status: REAL (policy + lifecycle engine); MOCK where it stands in
for a legal/DPO act (the legal-hold flag is a seeded stand-in for a real legal decision).

Design:
  - Each record is tagged with a PURPOSE (why it was collected). Each purpose has a
    bounded retention period (purpose limitation + data minimization).
  - ``apply_lifecycle`` deletes records past their purpose-bound retention as of a clock.
  - ``erase`` honours a data-principal erasure request BUT applies carve-outs: records
    under a legal hold or tied to an active fraud investigation are RETAINED (DPDP
    carve-out for legal/fraud-investigation obligations). Carve-outs are auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional


class Purpose:
    """Purposes for which L0/derived data is collected (purpose limitation)."""

    FRAUD_DETECTION = "fraud_detection"      # the core detection purpose
    INVESTIGATION = "investigation"          # active case material
    AUDIT = "audit"                          # immutable audit/WORM trail
    MODEL_TRAINING = "model_training"        # curated training snapshots
    OPERATIONAL_METRICS = "operational_metrics"  # short-lived ops telemetry


# Purpose-bound retention periods (days). Aligned to RBI record-keeping (longer audit)
# and DPDP minimization (shorter ops). These are the documented timelines.
RETENTION_DAYS: dict[str, int] = {
    Purpose.FRAUD_DETECTION: 365,        # 1y of behavioural history for baselines
    Purpose.INVESTIGATION: 365 * 8,      # long retention for case material (RBI/legal)
    Purpose.AUDIT: 365 * 10,             # immutable audit trail (decade)
    Purpose.MODEL_TRAINING: 365 * 3,     # versioned training snapshots
    Purpose.OPERATIONAL_METRICS: 30,     # short-lived ops telemetry (minimization)
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Record:
    """A retention-managed record (an L0 event id or a derived artifact)."""

    record_id: str
    subject_id: str               # the data principal this record concerns (EMP-*/ACCT-*)
    purpose: str
    created_at: datetime
    legal_hold: bool = False      # MOCK: seeded stand-in for a real legal-hold decision
    under_investigation: bool = False  # tied to an active fraud case

    def expires_at(self) -> datetime:
        days = RETENTION_DAYS.get(self.purpose, 365)
        return self.created_at + timedelta(days=days)

    def is_expired(self, as_of: Optional[datetime] = None) -> bool:
        return (as_of or _now()) >= self.expires_at()

    def is_carved_out(self) -> bool:
        """Carve-out: legal hold OR active investigation -> must NOT be deleted/erased."""
        return self.legal_hold or self.under_investigation


@dataclass
class LifecycleResult:
    deleted: list[str] = field(default_factory=list)
    retained: list[str] = field(default_factory=list)
    carved_out: list[str] = field(default_factory=list)


def apply_lifecycle(
    records: Iterable[Record], as_of: Optional[datetime] = None
) -> tuple[list[Record], LifecycleResult]:
    """Automated lifecycle deletion: drop records past their purpose-bound retention,
    UNLESS carved out (legal hold / active investigation). Returns (surviving, result)."""
    as_of = as_of or _now()
    surviving: list[Record] = []
    res = LifecycleResult()
    for r in records:
        if r.is_expired(as_of):
            if r.is_carved_out():
                surviving.append(r)
                res.carved_out.append(r.record_id)
            else:
                res.deleted.append(r.record_id)
        else:
            surviving.append(r)
            res.retained.append(r.record_id)
    return surviving, res


@dataclass
class ErasureResult:
    erased: list[str] = field(default_factory=list)
    withheld: list[str] = field(default_factory=list)  # carved out, not erased
    reason: dict[str, str] = field(default_factory=dict)


def erase(
    records: Iterable[Record], subject_id: str
) -> tuple[list[Record], ErasureResult]:
    """Honour a data-principal erasure request for ``subject_id`` WITH carve-outs.

    Records concerning the subject are erased EXCEPT those under a legal hold or active
    fraud investigation, which are withheld (DPDP carve-out for legal/fraud obligations).
    Returns (surviving_records, result). The withheld set is auditable.
    """
    surviving: list[Record] = []
    res = ErasureResult()
    for r in records:
        if r.subject_id != subject_id:
            surviving.append(r)
            continue
        if r.is_carved_out():
            surviving.append(r)
            res.withheld.append(r.record_id)
            res.reason[r.record_id] = (
                "legal_hold" if r.legal_hold else "active_investigation"
            )
        else:
            res.erased.append(r.record_id)
    return surviving, res


def _demo_records() -> list[Record]:
    """Tiny demo set for tests: one expired/erasable, one expired-but-carved-out.

    Both records are past the 30-day OPERATIONAL_METRICS retention; ``r-case`` is also
    flagged under active investigation, so lifecycle deletion must carve it out while
    ``r-ops`` is deleted/erased.
    """
    old = _now() - timedelta(days=400)
    return [
        Record("r-ops", "EMP-aaaa", Purpose.OPERATIONAL_METRICS, old),
        Record("r-case", "EMP-aaaa", Purpose.OPERATIONAL_METRICS, old,
               under_investigation=True),
    ]
