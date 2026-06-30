"""Tests for the governance backbone (PLATFORM-32/34/41)."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "governance" / "validation"))

import seed as seed_mod       # governance/db/seed.py (conftest path)
import signoff_gate           # governance/validation/signoff_gate.py
from govapi.main import app   # services/governance-api/govapi/main.py

client = TestClient(app)


def _seed():
    seed_mod.main()


def test_go_live_gate_is_go_after_seed():
    _seed()
    r = client.get("/api/v1/go-live")
    assert r.status_code == 200
    body = r.json()
    assert body["gate"] == "GO"
    assert body["met"] == body["total"] == 17


def test_policies_include_board_approved_ai_policy():
    _seed()
    r = client.get("/api/v1/governance/policies")
    assert r.status_code == 200
    types = {p["policy_type"] for p in r.json()["records"]}
    assert "ai_policy" in types
    ai = [p for p in r.json()["records"] if p["policy_type"] == "ai_policy"][0]
    assert ai["status"] == "board_approved" and ai["resolution_id"]


def test_board_pack_rollup():
    _seed()
    r = client.get("/api/v1/governance/board-pack")
    b = r.json()
    assert b["vapt_passed"] is True
    assert b["vendors_assessed"] >= 3
    assert b["models_validated"] >= 1


def test_unknown_artifact_404():
    assert client.get("/api/v1/governance/nope").status_code == 404


def test_incident_reporting_form_creates_record():
    _seed()
    r = client.post("/api/v1/governance/incidents",
                    json={"description": "drift spike on L3", "incident_type": "ai_model"})
    assert r.status_code == 200 and r.json()["incident_id"]


def test_signoff_gate_allows_validated_version():
    _seed()
    r = signoff_gate.check("fusion-2026.2.0")
    assert r["allowed"] is True
    assert r["validator"] is not None


def test_signoff_gate_blocks_unvalidated_version():
    _seed()
    r = signoff_gate.check("totally-unknown-9.9.9")
    assert r["allowed"] is False
    assert any("validation" in reason for reason in r["reasons"])
