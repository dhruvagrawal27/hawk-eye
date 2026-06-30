"""Date helpers for regulatory windows (BACKEND-24/25). Decoupled from the API app."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

THREE_CRORE_INR = 3_00_00_000  # ₹3 crore = 30,000,000 (CRILC reporting trigger)
CRILC_REPORTING_DAYS = 7  # report to CRILC within 7 days of the trigger
CRILC_CLASSIFICATION_DAYS = 180  # 180-day classification window


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def add_days(ts: str, days: int) -> str:
    return iso_z(parse(ts) + timedelta(days=days))
