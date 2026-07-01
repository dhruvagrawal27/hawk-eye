"""Phase 3 — Entity-360. The unified timeline now carries an authoritative `is_off_hours` flag on
every row (IST bank-hours), so the activity heatmap can colour off-hours activity — a first-order
insider signal that was previously not surfaced per-event."""

from __future__ import annotations

from app.routes.entity_routes import _is_off_hours_ist


def test_off_hours_derivation_ist_bank_hours():
    # 02:14 IST on a weekday = 2026-06-29T20:44Z (Mon) → off-hours.
    assert _is_off_hours_ist("2026-06-29T20:44:00Z") is True
    # 14:00 IST on a weekday = 2026-06-30T08:30Z (Tue) → bank hours.
    assert _is_off_hours_ist("2026-06-30T08:30:00Z") is False
    # bad timestamp → safe default
    assert _is_off_hours_ist("not-a-time") is False


def test_timeline_rows_expose_is_off_hours(client, auth):
    r = client.get("/api/v1/entities/EMP-7f3a/timeline", headers=auth("analyst"))
    assert r.status_code == 200
    events = r.json()["events"]
    assert events, "expected a seeded timeline for the worked-burst entity"
    for ev in events:
        assert "is_off_hours" in ev
        assert isinstance(ev["is_off_hours"], bool)
