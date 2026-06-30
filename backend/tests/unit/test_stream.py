"""Live stream (BACKEND-13): the /ws/alerts WebSocket emits real scored ticks + alerts in inprocess
mode — no Kafka/Redis needed. Proves the online topology end-to-end (event → ONLINE → broadcast)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

TICK_KEYS = {"type", "tick_id", "employee_id", "score", "risk_level", "is_alert", "amount", "ts"}


def test_ws_alerts_streams_scored_events_and_alerts() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/alerts") as ws:
            ticks = 0
            alerts = 0
            for _ in range(12):
                msg = ws.receive_json()
                assert msg["type"] in ("event.scored", "alert.new")
                if msg["type"] == "event.scored":
                    ticks += 1
                    assert TICK_KEYS.issubset(msg.keys())
                    assert 0 <= msg["score"] <= 100
                    assert msg["risk_level"] in ("low", "medium", "high", "critical")
                else:
                    alerts += 1
                    a = msg["alert"]
                    # the alert.new payload is a real Alert produced by the ONLINE pipeline
                    assert {"alert_id", "entity_id", "risk_score", "severity"}.issubset(a.keys())
                    assert a["risk_score"] >= 70  # alerts only above the emit threshold
            assert ticks >= 1
            # the front-loaded "mule burst" should have produced at least one real alert quickly
            assert alerts >= 1


def test_stream_status_endpoint() -> None:
    with TestClient(app) as client:
        r = client.get("/api/v1/stream/status")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] in ("inprocess", "kafka", "off")
        assert "events_published" in body
