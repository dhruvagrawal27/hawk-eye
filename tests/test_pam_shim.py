"""Unit tests for the PAM shim (PLATFORM-15, Part 19.3, MOCK)."""

import importlib

from fastapi.testclient import TestClient

main = importlib.import_module(
    "pamsvc.main"
)  # services/pam-shim/pamsvc/main.py (conftest path)
client = TestClient(main.app)


def test_shared_account_rejected():
    for acct in ("root", "admin", "shared", "service", ""):
        r = client.post(
            "/sessions/start",
            json={"admin": acct, "role": "platform_admin", "reason": "x"},
        )
        assert r.status_code == 403, acct


def test_named_admin_session_records_and_enforces_least_privilege():
    r = client.post(
        "/sessions/start",
        json={
            "admin": "arun.k",
            "role": "platform_admin",
            "reason": "rotate NEAR key (TICKET-42)",
        },
    )
    assert r.status_code == 200
    sid = r.json()["session_id"]

    ok = client.post(
        f"/sessions/{sid}/command",
        json={"command": "rotate_secret", "target": "NEAR_AI_API_KEY"},
    )
    assert ok.status_code == 200 and ok.json()["recorded"] is True

    denied = client.post(
        f"/sessions/{sid}/command",
        json={"command": "drop_database", "target": "governance"},
    )
    assert denied.status_code == 403  # least-privilege blocks it

    end = client.post(f"/sessions/{sid}/end")
    assert end.status_code == 200
    body = end.json()
    assert body["command_count"] == 2 and body["denied_count"] == 1
    assert body["recording_uri"].startswith("worm://")


def test_reason_required():
    r = client.post(
        "/sessions/start",
        json={"admin": "arun.k", "role": "platform_admin", "reason": "  "},
    )
    assert r.status_code == 400


def test_session_appears_in_audit_view():
    client.post(
        "/sessions/start",
        json={"admin": "iqbal.s", "role": "security_admin", "reason": "rotate"},
    )
    r = client.get("/sessions")
    assert any(s["admin"] == "iqbal.s" for s in r.json()["sessions"])
