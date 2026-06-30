"""Alert payload + queue contract (BACKEND-4/19, blueprint Part 24.5b)."""

from __future__ import annotations

from app.schemas.alerts import Alert
from app.schemas.common import Severity


def test_alert_example_matches_24_5b():
    a = Alert(**Alert.example())
    assert a.alert_id.startswith("alr_")
    assert a.entity_id == "EMP-7f3a"
    assert a.risk_score == 87 and 0 <= a.risk_score <= 100
    assert a.severity == Severity.HIGH.value
    assert 0.0 <= a.confidence <= 1.0
    assert a.contributing_layers and a.reason_codes
    assert a.exposure_inr == 4_800_000
    assert a.pii_tokenized is True
    # every reason code carries a source in {rule, shap, graph, sequence}
    assert all(rc.source in ("rule", "shap", "graph", "sequence") for rc in a.reason_codes)


def test_get_alert_shape(client, auth):
    h = auth("senior")
    r = client.get("/api/v1/alerts/alr_demo01", headers=h)
    assert r.status_code == 200
    body = r.json()
    for field in (
        "alert_id",
        "entity_id",
        "risk_score",
        "severity",
        "confidence",
        "status",
        "created_ts",
        "contributing_layers",
        "reason_codes",
        "exposure_inr",
        "sla_due_ts",
        "pii_tokenized",
    ):
        assert field in body, field
    assert body["created_ts"].endswith("Z")


def test_queue_ranked_by_fused_risk_exposure_confidence(client, auth):
    r = client.get("/api/v1/alerts", headers=auth("senior"))
    items = r.json()["items"]
    assert items[0]["alert_id"] == "alr_demo04"  # 93 × 35M × .88 ranks first


def test_queue_deduped_per_entity():
    from app.schemas.alerts import Alert
    from app.store.alert_store import ALERTS

    # Two alerts for the same entity → the queue shows one (deduped per entity).
    ALERTS.add(
        Alert(
            **{
                **Alert.example(),
                "alert_id": "alr_dupeA",
                "entity_id": "EMP-dupe",
                "risk_score": 70,
            }
        )
    )
    ALERTS.add(
        Alert(
            **{
                **Alert.example(),
                "alert_id": "alr_dupeB",
                "entity_id": "EMP-dupe",
                "risk_score": 90,
            }
        )
    )
    items, _ = ALERTS.query(dedupe_per_entity=True, limit=100)
    dupe_ids = [a.alert_id for a in items if a.entity_id == "EMP-dupe"]
    assert dupe_ids == ["alr_dupeB"]  # the higher-ranked one survives


def test_case_scope_relationship_manager_sees_only_assigned(client, auth):
    # Relationship Manager (view = assigned_only) sees fewer alerts than the Branch Manager (all).
    rm_total = client.get("/api/v1/alerts", headers=auth("analyst")).json()["total"]
    branch_total = client.get("/api/v1/alerts", headers=auth("senior")).json()["total"]
    assert rm_total < branch_total  # need-to-know
