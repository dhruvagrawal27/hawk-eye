"""Synthetic seed data (ON-PREM + SYNTHETIC ONLY).

Seeds the canonical worked-burst alert (Part 24.5b, ``alr_demo01``) plus a couple more alerts and
the entity-360 surface for EMP-7f3a so the triage queue, entity timeline, graph, peers, and
explanation panels render immediately. Idempotent. No real PII.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

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
from app.schemas.risk_index import RiskIndexComponent, RiskIndexResponse
from app.pii.vault import VAULT
from app.store.alert_store import ALERTS
from app.store.entity_store import ENTITIES
from app.store.user_store import USER_STORE
from app.workflow.escalation import apply_sla

DEMO_ALERT_ID = "alr_demo01"

# token → (synthetic real value, field_type). The seeded alerts/entity-360 reference these
# already-tokenized IDs directly (the tokenizer never ran at ingest for the demo data), so the
# re-id vault would otherwise be empty and POST /entities/{id}/unmask would return {}. Populating
# it here gives authorized (audited) unmask a real (SYNTHETIC) value to return. No real PII.
_DEMO_REID: dict[str, tuple[str, str]] = {
    # employees (field_type "employee")
    "EMP-7f3a": ("Rohit Mehra (Ops Maker, Trade Finance, BR-219)", "employee"),
    "EMP-1a09": ("Anita Desai (Ops Checker, Trade Finance, BR-219)", "employee"),
    "EMP-2b14": ("Vikram Nair (Payments Maker, BR-104)", "employee"),
    "EMP-3c55": ("Suresh Rao (DBA, Core Banking, BR-001)", "employee"),
    "EMP-4d99": ("Priya Kulkarni (Ops Maker, BR-330)", "employee"),
    "EMP-9f02": ("Manish Gupta (former Ops Maker / leaver, BR-219)", "employee"),
    # beneficiaries (field_type "beneficiary")
    "BEN-9b1c": ("Sunrise Traders (payee, HDFC ****4471)", "beneficiary"),
    "BEN-77aa": ("Orbit Exports Pvt Ltd (payee, ICICI ****9920)", "beneficiary"),
    # accounts (field_type "account")
    "ACCT-4d22": ("HDFC0002841 / 5011****4471", "account"),
    "ACCT-77a1": ("SBIN0001102 / 3099****7712", "account"),
}


def _seed_reid_vault() -> None:
    """Populate the re-id vault with token→(synthetic) real mappings for demo tokens (idempotent)."""
    for token, (real_value, field_type) in _DEMO_REID.items():
        VAULT.store(token, real_value, field_type)


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
    # M2.1 demo insider-risk index (in prod the ML batch job writes this; seeded for the demo).
    ENTITIES.put_risk_index(
        RiskIndexResponse(
            employee_id="EMP-7f3a",
            composite=78,
            hr_score=0.55,
            access_score=0.48,
            anomaly_score=0.72,
            components=[
                RiskIndexComponent(name="offhours_score", group="anomaly", value=0.72,
                                   detail="off-hours activity"),
                RiskIndexComponent(name="recent_alerts_30d", group="anomaly", value=0.6,
                                   detail="alerts in the last 30 days"),
                RiskIndexComponent(name="role_change_recency", group="hr", value=0.5,
                                   detail="recent role change"),
                RiskIndexComponent(name="standing_privilege", group="access", value=0.4,
                                   detail="unexercised held entitlements"),
            ],
            top_drivers=["offhours_score", "recent_alerts_30d", "role_change_recency"],
            updated_ts="2026-06-30T06:00:00Z",
            calibrated=False,
        )
    )


# Bulk demo alerts so the dashboard/queue read at real-bank scale (hundreds), not a handful. All
# synthetic; NONE are confirmed_fraud (keeps FMR/CFR/CRILC counts driven only by the curated cases).
_BULK_SIGNALS: tuple[tuple[str, str], ...] = (
    ("NEW_BENEFICIARY_THEN_HIGHVALUE", "new payee paid a high value within the hour"),
    ("OFF_HOURS_ACTIVITY", "privileged action outside business hours"),
    ("DB_WRITE_WITHOUT_APP_TXN", "direct database write with no application transaction"),
    ("ENTITLEMENT_SELF_GRANT", "actor granted themselves an entitlement"),
    ("PRIVILEGED_SESSION_CORRELATION", "bulk export inside a privileged session"),
    ("DORMANT_REACTIVATION_DRAIN", "dormant account reactivated then drained"),
    ("SWIFT_CBS_MISMATCH", "SWIFT instrument with no reconciling CBS transaction"),
    ("LEAVER_WINDOW_EXFIL", "bulk data export during the leaver's notice window"),
)
# Active workflow states (count as "open"); a minority resolve as FP/closed/inconclusive.
_BULK_ACTIVE = (
    AlertStatus.OPEN,
    AlertStatus.OPEN,
    AlertStatus.OPEN,
    AlertStatus.ASSIGNED,
    AlertStatus.ASSIGNED,
    AlertStatus.IN_REVIEW,
)
_BULK_RESOLVED = (AlertStatus.FALSE_POSITIVE, AlertStatus.CLOSED, AlertStatus.INCONCLUSIVE)


def _seed_bulk_alerts(count: int = 450) -> None:
    """Seed `count` synthetic alerts across `count` distinct entities (so per-entity dedupe keeps
    them all), with varied severity / status / SLA / exposure. Deterministic; exposures stay under
    ₹3 crore and no alert is confirmed_fraud, so regulatory (FMR/CFR/CRILC) figures are unaffected."""
    now = datetime.now(timezone.utc)
    for i in range(count):
        risk = 45 + (i * 7 + 13) % 52  # 45–96, spread across medium/high
        severity = Severity.HIGH if risk >= 70 else Severity.MEDIUM
        status = _BULK_RESOLVED[i % len(_BULK_RESOLVED)] if i % 7 == 0 else _BULK_ACTIVE[i % len(_BULK_ACTIVE)]
        days_ago = i % 40  # SLA spread: ~30% land within 3 days of / past the 30-day RBI deadline
        created = (now - timedelta(days=days_ago)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        code, detail = _BULK_SIGNALS[i % len(_BULK_SIGNALS)]
        layers = ["L1_rules", "L2_unsupervised", "L3_gbdt"]
        if i % 3 == 0:
            layers.append("L5_graph")
        if i % 4 == 0:
            layers.append("L4_sequence")
        alert = Alert(
            alert_id=f"alr_bulk{i:04d}",
            entity_id=f"EMP-x{i:04d}",
            risk_score=risk,
            severity=severity,
            confidence=round(0.5 + (i % 45) / 100.0, 2),
            status=status,
            created_ts=created,
            contributing_layers=layers,
            reason_codes=[
                {"source": "rule", "code": code, "detail": detail},
                {"source": "shap", "feature": "amount_zscore", "contribution": round(0.1 + (i % 7) / 20.0, 2)},
            ],
            exposure_inr=200_000 + (i % 45) * 100_000,  # ₹2L–₹46L (< ₹3 crore)
            sla_due_ts=None,
            pii_tokenized=True,
        )
        apply_sla(alert)
        ALERTS.add(alert)


def seed_demo() -> None:
    """Idempotent: populate demo alerts + entity-360 if not already present."""
    # Always (re)seed the re-id vault first — it is separate from the alert store, so it must be
    # populated even when the alerts already exist (e.g. after a restart that reloaded alerts).
    _seed_reid_vault()
    # Ambient sub-threshold population ('hidden 95%') — reseeded every call (cleared on reset) so the
    # detection funnel + near-miss watchlist are never empty; the live pipeline also records into it.
    from app.store.analytics_store import seed_analytics
    from app.store.subthreshold_store import seed_subthreshold

    seed_subthreshold()
    seed_analytics()  # fraud-typology prevalence + confirmed-rate (management analytics)
    # Entity-360 lives in the in-memory ENTITIES store (never persisted), so — like the re-id vault
    # above — it must be reseeded on every boot even when the alerts already exist. Otherwise a
    # restart that reloads alerts from the sqlite store trips the guard below and leaves the
    # entity-360 surface empty (GET /entities/{id} -> 404 for every entity, incl. worked-burst
    # EMP-7f3a). put_* is idempotent (dict overwrite), so calling this every time is safe.
    _seed_entity_360()
    if ALERTS.get(DEMO_ALERT_ID) is not None:
        return
    for builder in (_demo_alert, _second_alert, _third_alert, _fourth_alert):
        alert = builder()
        if alert.sla_due_ts is None:
            apply_sla(alert)
        ALERTS.add(alert)
    # Bulk synthetic alerts so the console reads at real-bank scale (hundreds). Default ON; the test
    # harness sets HAWKEYE_SEED_BULK=0 for fast, deterministic reseeds. (Entity-360 is reseeded above
    # the idempotency guard so it survives restarts.)
    if os.getenv("HAWKEYE_SEED_BULK", "1") != "0":
        _seed_bulk_alerts()
    # Relationship Manager case scope: assign the demo alerts to the seeded RM (need-to-know).
    # EMP-an01 is the legacy analyst→relationship_manager login alias (docs/BANK_ROLES.md).
    USER_STORE.assign_alert("EMP-an01", "alr_demo01")
    USER_STORE.assign_alert("EMP-an01", "alr_demo02")
    ALERTS.assign("alr_demo02", "EMP-an01")
