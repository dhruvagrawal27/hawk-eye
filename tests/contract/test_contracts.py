"""Contract tests (PLATFORM-16, blueprint Part 31.1). Verify PLATFORM-owned outputs match the
canonical contract in BACKEND.md (alert schema §2, audit memo §7) and that governance-api
serves the routes the dashboard depends on."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for p in ("services/degradation-switch", "services/tee-attestation"):
    sys.path.insert(0, str(ROOT / p))

from dswitch import scoring          # noqa: E402
from teesvc import attestation       # noqa: E402
import seed as seed_mod              # noqa: E402
from govapi.main import app          # noqa: E402

client = TestClient(app)

# BACKEND.md §2 — required L6 alert fields.
ALERT_FIELDS = {"alert_id", "entity_id", "risk_score", "severity", "confidence",
                "status", "contributing_layers", "reason_codes", "exposure_inr", "pii_tokenized"}
# BACKEND.md §7 — narrative/attestation audit-memo fields.
AUDIT_MEMO_FIELDS = {"provider", "tee_attested", "attestation_id", "model", "prompt_hash", "ts"}

FRAUD = {
    "event_id": "evt_c1", "ts": "2026-06-30T02:14:07Z",
    "actor": {"employee_id": "EMP-7f3a"}, "action": {"verb": "approve_payment", "maker_checker": "checker"},
    "object": {"beneficiary_id": "BEN-9b1c", "amount": 4_800_000, "new_beneficiary": True, "beneficiary_age_min": 27},
    "context": {"is_off_hours": True},
}


def test_alert_matches_backend_contract():
    a = scoring.score_event(FRAUD, "rules_only")
    assert ALERT_FIELDS.issubset(a.keys()), ALERT_FIELDS - a.keys()
    assert a["alert_id"].startswith("alr_")
    assert a["severity"] in {"low", "medium", "high", "critical"}
    assert isinstance(a["risk_score"], int) and 0 <= a["risk_score"] <= 100
    assert a["pii_tokenized"] is True


def test_tee_audit_memo_matches_backend_contract():
    rep = attestation.issue_quote("tokenized EMP-7f3a", model="openai/gpt-oss-120b",
                                  provider="near_ai", enclave_mode=True)
    assert AUDIT_MEMO_FIELDS.issubset(rep.keys()), AUDIT_MEMO_FIELDS - rep.keys()


def test_governance_api_serves_dashboard_routes():
    seed_mod.main()
    for route in ("/api/v1/governance/policies", "/api/v1/governance/committees",
                  "/api/v1/governance/board-pack", "/api/v1/go-live"):
        assert client.get(route).status_code == 200, route


def test_go_live_contract_shape():
    seed_mod.main()
    body = client.get("/api/v1/go-live").json()
    assert {"gate", "met", "total", "by_category", "threat_intel_feedback"}.issubset(body.keys())
    assert body["gate"] in {"GO", "NO-GO"}
