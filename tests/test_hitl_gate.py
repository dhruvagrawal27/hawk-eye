"""Tests for the HITL natural-justice gate (PLATFORM-37) — proves ALERT-ONLY in software."""

from fastapi.testclient import TestClient

import models  # governance models (conftest path)
import seed as seed_mod
from hitlsvc.main import app

client = TestClient(app)

CLS = {
    "alert_id": "alr_3d7e22",
    "entity_id": "EMP-7f3a",
    "risk_score": 87,
    "severity": "high",
    "reason_codes": [{"source": "rule", "code": "NEW_BENEFICIARY_THEN_HIGHVALUE"}],
    "proportionality": "Monitors only risk-relevant maker-checker + payment signals (Part 29.2).",
    "explanation": "New payee paid INR 48,00,000 off-hours, 27 min after onboarding.",
    "model_version": "fusion-2026.2.0",
}


def test_classification_held_pending_review_then_human_decides():
    seed_mod.main()  # ensures an approved DPIA exists (binding)
    r = client.post("/api/v1/classifications", json=CLS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending_review"  # ALERT-ONLY: not auto-acted
    cid = body["classification_id"]

    # queue shows it pending
    q = client.get("/api/v1/classifications?status=pending_review")
    assert any(c["classification_id"] == cid for c in q.json()["classifications"])

    # detail shows proportionality + explanation (contestable — natural justice)
    d = client.get(f"/api/v1/classifications/{cid}").json()
    assert d["proportionality"] and d["explanation"]

    # human approves -> alert raised for human action, NEVER an auto-block
    dec = client.post(
        f"/api/v1/classifications/{cid}/decision",
        json={
            "decision": "approve",
            "reviewer": "Asha (analyst)",
            "justification": "Confirmed shell beneficiary; refer to Vigilance.",
        },
    )
    out = dec.json()
    assert out["status"] == "reviewed_confirmed"
    assert out["outcome"] == "alert_raised_for_human_action"
    assert "auto-block" not in str(out).lower() or "never auto-block" in out["note"]


def test_decision_requires_justification():
    seed_mod.main()
    cid = client.post("/api/v1/classifications", json=CLS).json()["classification_id"]
    r = client.post(
        f"/api/v1/classifications/{cid}/decision",
        json={"decision": "approve", "reviewer": "x", "justification": "  "},
    )
    assert r.status_code == 400


def test_blocked_without_dpia_signoff(tmp_path, monkeypatch):
    """Natural-justice binding (Part 28): no approved DPIA -> cannot process classification."""
    empty_db = f"sqlite:///{tmp_path}/empty.db"
    monkeypatch.setattr(models, "DB_URL", empty_db)
    models.init_db(empty_db)  # tables exist but DPIA is empty
    r = client.post("/api/v1/classifications", json=CLS)
    assert r.status_code == 412
