"""Shared DATA conventions: IDs, topics, time, money, feature-key naming.

These are the cross-cutting decisions other DATA modules import. Conventions match
CONTEXT.md §6 and BACKEND.md. Announce any change here in CONTEXT.md.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

# ---- ID conventions (CONTEXT.md §6 / BACKEND.md) ----------------------------
ID_PREFIXES = {
    "event": "evt_",
    "alert": "alr_",
    "employee": "EMP-",   # entity_id == employee_id
    "account": "ACCT-",
    "beneficiary": "BEN-",
    "ring": "RNG-",
    "audit": "aud_",
    "session": "sess_",
    "vendor": "VEN-",
}


def make_id(kind: str, *parts: object) -> str:
    """Deterministic, readable id from a stable hash of `parts`.

    Deterministic so the simulator is reproducible and event_ids are idempotent
    (DATA-5 normalizer requires deterministic event_id for dedupe; DATA-17).
    """
    prefix = ID_PREFIXES[kind]
    raw = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}{digest}"


# ---- Kafka topics (DATA-3) --------------------------------------------------
class Topics:
    EVENTS_RAW = "events.raw"
    EVENTS_SIGNALS = "events.signals"   # recon / derived signals (DATA-16)
    ALERTS = "alerts"
    AUDIT = "audit"


# ---- Service ports (CONTEXT.md §7; PLATFORM-provisioned, we consume) --------
class Ports:
    KAFKA = 9092
    CLICKHOUSE_HTTP = 8123
    CLICKHOUSE_NATIVE = 9000
    REDIS = 6379
    MINIO_API = 9001
    MINIO_CONSOLE = 9002


# ---- Time / money -----------------------------------------------------------
CURRENCY_DEFAULT = "INR"
# Off-hours window (local branch time): outside 08:00-20:00 on weekdays, all weekend.
OFF_HOURS_START = 20  # 20:00
OFF_HOURS_END = 8     # 08:00


def is_off_hours(hour: int, weekday: int) -> bool:
    """weekday: 0=Mon .. 6=Sun. Off-hours = nights + weekends."""
    if weekday >= 5:
        return True
    return hour >= OFF_HOURS_START or hour < OFF_HOURS_END


# ---- Feature-key naming convention (DATA-19/20/21; published in CONTEXT.md) --
# Format: "<entity>:<feature>:<window>"  e.g. "EMP-7f3a:offhours_score:30d"
def feature_key(entity_id: str, feature: str, window: str = "all") -> str:
    return f"{entity_id}:{feature}:{window}"


# ---- Lanes (DATA-9; Part 12 coverage map) -----------------------------------
LANE_FAST = "fast"
LANE_SLOW = "slow"


@dataclass(frozen=True)
class SimConfig:
    """Scale knobs for the simulator (DATA-10). Defaults are small for fast local runs."""
    n_employees: int = 500
    privileged_fraction: float = 0.02
    days: int = 60                  # production target ~18 months; small default for local runs
    fraud_actor_rate: float = 0.01  # ~0.1-1% of actors are fraudulent (keep rare)
    seed: int = 1405
    out_dir: str = "data/out"
