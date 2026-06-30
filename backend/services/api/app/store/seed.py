"""Synthetic seed data (ON-PREM + SYNTHETIC ONLY).

Seeds the canonical worked-burst alert (Part 24.5b, ``alr_demo01``) plus a couple more alerts and
the entity-360 surface for EMP-7f3a so the triage queue, entity timeline, graph, peers, and
explanation panels render immediately. Idempotent. No real PII.
"""

from __future__ import annotations

from app.schemas.alerts import Alert
from app.schemas.common import AlertStatus, Severity
from app.schemas.entities import (
    EntityGraph,
    EntityProfile,
    GraphEdge,
    GraphNode,
    PeerComparison,
    TimelineEvent,
)
from app.store.alert_store import ALERTS
from app.store.entity_store import ENTITIES
from app.store.user_store import USER_STORE
from app.workflow.escalation import apply_sla

DEMO_ALERT_ID = "alr_demo01"


def _demo_alert() -> Alert:
    payload = Alert.example()
    payload["alert_id"] = DEMO_ALERT_ID
    alert = Alert(**payload)
    alert.ring_id = "RNG-12"
    alert.model_versions = {
        "L2_unsupervised": "l2_isoforest@stub-2026.06.30",
        "L3_gbdt": "l3_lightgbm@stub-2026.06.30",
        "L6_fusion": "l6_meta@stub-2026.06.30",
    }
    apply_sla(alert)
    return alert


def _second_alert() -> Alert:
    return Alert(
        alert_id="alr_demo02",
        entity_id="EMP-2b14",
        risk_score=58,
        severity=Severity.MEDIUM,
        confidence=0.64,
        status=AlertStatus.OPEN,
        created_ts="2026-06-29T19:05:00Z",
        contributing_layers=["L1_rules", "L2_unsupervised"],
        reason_codes=[
            {
                "source": "rule",
                "code": "JUST_UNDER_THRESHOLD",
                "detail": "amount INR 9,80,000 structured just below threshold INR 10,00,000",
            },
            {"source": "shap", "feature": "amount_zscore", "contribution": 0.18},
        ],
        exposure_inr=980000,
        sla_due_ts=None,
        pii_tokenized=True,
    )


def _third_alert() -> Alert:
    return Alert(
        alert_id="alr_demo03",
        entity_id="EMP-3c55",
        risk_score=81,
        severity=Severity.HIGH,
        confidence=0.77,
        status=AlertStatus.OPEN,
        created_ts="2026-06-30T01:02:00Z",
        contributing_layers=["L1_rules", "L3_gbdt", "L5_graph"],
        reason_codes=[
            {
                "source": "rule",
                "code": "DB_WRITE_WITHOUT_APP_TXN",
                "detail": "direct DB write ACCT-77a1 with no matching application transaction",
            },
            {
                "source": "rule",
                "code": "PRIVILEGED_SESSION_CORRELATION",
                "detail": "privileged session for EMP-3c55 correlated with off-hours DB activity",
            },
            {"source": "graph", "detail": "EMP-3c55 shares device WS-114 with leaver EMP-9f02"},
        ],
        exposure_inr=2500000,
        sla_due_ts=None,
        pii_tokenized=True,
    )


def _fourth_alert() -> Alert:
    """A previously-confirmed high-exposure fraud (≥ ₹3 crore) so CRILC/FMR exports are non-empty."""
    return Alert(
        alert_id="alr_demo04",
        entity_id="EMP-4d99",
        risk_score=93,
        severity=Severity.HIGH,
        confidence=0.88,
        status=AlertStatus.CONFIRMED_FRAUD,
        created_ts="2026-06-28T11:20:00Z",
        contributing_layers=["L1_rules", "L3_gbdt", "L5_graph"],
        reason_codes=[
            {
                "source": "rule",
                "code": "NEW_BENEFICIARY_THEN_HIGHVALUE",
                "detail": "new payee BEN-77aa paid INR 3,50,00,000 within 41 min",
            },
            {"source": "graph", "detail": "beneficiary BEN-77aa in mule ring RNG-44"},
        ],
        exposure_inr=35000000,  # ₹3.5 crore → CRILC-reportable
        sla_due_ts=None,
        pii_tokenized=True,
    )


def _seed_entity_360() -> None:
    ENTITIES.put_profile(
        EntityProfile(
            entity_id="EMP-7f3a",
            role="ops_maker",
            dept="trade_finance",
            branch="BR-219",
            peer_group="PG-ops-tf",
            tenure_days=2840,
            privileged_flag=False,
            leaver_flag=False,
            risk_score=87,
            severity=Severity.HIGH,
            open_alerts=1,
            pii_tokenized=True,
        )
    )
    ENTITIES.put_timeline(
        "EMP-7f3a",
        [
            TimelineEvent(
                ts="2026-06-30T02:14:07Z",
                lane="change",
                verb="create_beneficiary",
                channel="cbs",
                detail="new payee BEN-9b1c created (off-hours)",
                event_id="evt_8f2a1c90",
            ),
            TimelineEvent(
                ts="2026-06-30T02:33:10Z",
                lane="transaction",
                verb="approve_payment",
                channel="cbs",
                detail="INR 48,00,000 to BEN-9b1c (checker EMP-1a09)",
                event_id="evt_8f2a1d04",
                amount_inr=4800000,
            ),
            TimelineEvent(
                ts="2026-06-30T02:33:11Z",
                lane="access",
                verb="graph_update",
                detail="maker-checker edge EMP-7f3a↔EMP-1a09",
            ),
        ],
    )
    ENTITIES.put_graph(
        EntityGraph(
            entity_id="EMP-7f3a",
            ring_id="RNG-12",
            nodes=[
                GraphNode(id="EMP-7f3a", kind="employee", label="maker", risk=87),
                GraphNode(id="EMP-1a09", kind="employee", label="checker", risk=74),
                GraphNode(id="BEN-9b1c", kind="beneficiary", label="new payee", risk=66),
                GraphNode(id="ACCT-4d22", kind="account", label="payee account"),
            ],
            edges=[
                GraphEdge(source="EMP-7f3a", target="EMP-1a09", kind="maker_checker", weight=0.9),
                GraphEdge(source="EMP-7f3a", target="BEN-9b1c", kind="pays", weight=1.0),
                GraphEdge(source="BEN-9b1c", target="ACCT-4d22", kind="owns", weight=1.0),
            ],
        )
    )
    ENTITIES.put_peers(
        "EMP-7f3a",
        [
            PeerComparison(
                entity_id="EMP-7f3a",
                peer_group="PG-ops-tf",
                dimension="new_beneficiary_to_payment_latency_min",
                actor_value=27.0,
                peer_mean=2880.0,
                peer_p95=240.0,
                z_score=-3.1,
                is_outlier=True,
            ),
            PeerComparison(
                entity_id="EMP-7f3a",
                peer_group="PG-ops-tf",
                dimension="off_hours_activity_ratio",
                actor_value=0.42,
                peer_mean=0.03,
                peer_p95=0.12,
                z_score=3.6,
                is_outlier=True,
            ),
        ],
    )


def seed_demo() -> None:
    """Idempotent: populate demo alerts + entity-360 if not already present."""
    if ALERTS.get(DEMO_ALERT_ID) is not None:
        return
    for builder in (_demo_alert, _second_alert, _third_alert, _fourth_alert):
        alert = builder()
        if alert.sla_due_ts is None:
            apply_sla(alert)
        ALERTS.add(alert)
    _seed_entity_360()
    # Analyst case scope: assign the demo alerts to the seeded analyst (need-to-know).
    USER_STORE.assign_alert("EMP-an01", "alr_demo01")
    USER_STORE.assign_alert("EMP-an01", "alr_demo02")
    ALERTS.assign("alr_demo02", "EMP-an01")
