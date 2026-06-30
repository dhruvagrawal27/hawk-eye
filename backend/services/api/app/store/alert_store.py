"""Alert / case store (BACKEND-19/20/23).

# STUB: DATABASE (Postgres cases + ClickHouse score history). Holds alerts, dispositions, block
requests, narrative audit memos, and the feedback queue (DATA label-source-4 seam). Triage ranking
= fused risk × exposure × confidence, deduped per entity (Part 11 / 24.4).
"""

from __future__ import annotations

import json

from app.schemas.alerts import Alert
from app.schemas.common import AlertStatus, iso_z, utcnow
from app.schemas.narratives import NarrativeAuditMemo


def rank_key(alert: Alert) -> float:
    """Triage ranking score: fused risk × exposure × confidence."""
    return float(alert.risk_score) * max(int(alert.exposure_inr), 1) * float(alert.confidence)


class AlertStore:
    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}
        self._dispositions: dict[str, dict] = {}
        self._block_requests: dict[str, dict] = {}
        self._narrative_memos: list[NarrativeAuditMemo] = []
        self._feedback_queue: list[dict] = []  # labels queued for retraining (ML/DATA seam)

    # --- alerts ---
    def add(self, alert: Alert) -> Alert:
        self._alerts[alert.alert_id] = alert
        return alert

    def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    def all(self) -> list[Alert]:
        return list(self._alerts.values())

    def query(
        self,
        *,
        status: str | None = None,
        risk_gte: int | None = None,
        assignee: str | None = None,
        dedupe_per_entity: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Alert], int]:
        items = list(self._alerts.values())
        if status:
            items = [a for a in items if str(a.status) == status]
        if risk_gte is not None:
            items = [a for a in items if a.risk_score >= risk_gte]
        if assignee:
            items = [a for a in items if a.assignee == assignee]
        # rank by fused risk × exposure × confidence (desc)
        items.sort(key=rank_key, reverse=True)
        if dedupe_per_entity:
            seen: set[str] = set()
            deduped: list[Alert] = []
            for a in items:
                if a.entity_id in seen:
                    continue
                seen.add(a.entity_id)
                deduped.append(a)
            items = deduped
        total = len(items)
        return items[offset : offset + limit], total

    def assign(self, alert_id: str, assignee: str) -> Alert | None:
        alert = self._alerts.get(alert_id)
        if alert:
            alert.assignee = assignee
            if alert.status == AlertStatus.OPEN.value:
                # Alert uses model_config use_enum_values → status is stored as the str value.
                alert.status = AlertStatus.ASSIGNED.value  # type: ignore[assignment]
        return alert

    def set_status(self, alert_id: str, status: AlertStatus | str) -> Alert | None:
        alert = self._alerts.get(alert_id)
        if alert:
            value = status.value if isinstance(status, AlertStatus) else status
            alert.status = value  # type: ignore[assignment]
        return alert

    # --- dispositions / block requests ---
    def record_disposition(self, alert_id: str, record: dict) -> None:
        self._dispositions[alert_id] = record

    def get_disposition(self, alert_id: str) -> dict | None:
        return self._dispositions.get(alert_id)

    def record_block_request(self, alert_id: str, record: dict) -> None:
        self._block_requests[alert_id] = record

    # --- narrative memos (Part 25.4) ---
    def add_narrative_memo(self, memo: NarrativeAuditMemo) -> None:
        self._narrative_memos.append(memo)

    def narrative_memos(self, alert_id: str | None = None) -> list[NarrativeAuditMemo]:
        if alert_id:
            return [m for m in self._narrative_memos if m.alert_id == alert_id]
        return list(self._narrative_memos)

    # --- feedback loop (ML / DATA label-source-4) ---
    def queue_feedback(self, record: dict) -> None:
        self._feedback_queue.append(record)

    def feedback_queue(self) -> list[dict]:
        return list(self._feedback_queue)


class PersistedAlertStore(AlertStore):
    """AlertStore that mirrors writes to a durable backend and reloads on boot. The in-memory dict
    stays the fast query cache; the backend gives restart-survival + cross-worker sharing."""

    def __init__(self, backend) -> None:  # noqa: ANN001
        super().__init__()
        self._backend = backend
        for payload in backend.load_all():
            try:
                alert = Alert.model_validate(payload)
                self._alerts[alert.alert_id] = alert
            except Exception:  # noqa: BLE001 - skip an unparseable row, never crash boot
                continue

    def _row(self, alert: Alert) -> dict:
        return {
            "alert_id": alert.alert_id,
            "entity_id": alert.entity_id,
            "risk_score": int(alert.risk_score),
            "severity": str(alert.severity),
            "status": str(alert.status),
            "created_ts": str(alert.created_ts),
            "payload": json.dumps(alert.model_dump(mode="json")),
            "updated_at": iso_z(utcnow()),
        }

    def add(self, alert: Alert) -> Alert:
        super().add(alert)
        try:
            self._backend.upsert(self._row(alert))
        except Exception:  # noqa: BLE001 - a DB hiccup must never break the alert path
            pass
        return alert

    def assign(self, alert_id: str, assignee: str) -> Alert | None:
        alert = super().assign(alert_id, assignee)
        if alert:
            try:
                self._backend.upsert_assignee(alert_id, assignee, str(alert.status))
            except Exception:  # noqa: BLE001
                pass
        return alert

    def set_status(self, alert_id: str, status: AlertStatus | str) -> Alert | None:
        alert = super().set_status(alert_id, status)
        if alert:
            try:
                self._backend.upsert_status(alert_id, str(alert.status))
            except Exception:  # noqa: BLE001
                pass
        return alert


def _build_alert_store() -> AlertStore:
    """In-memory by default; durable (sqlite/postgres) when HAWKEYE_DB_URL is set."""
    from app.config import settings
    from app.store.persistence import make_backend

    backend = make_backend(settings.db_url)
    return PersistedAlertStore(backend) if backend is not None else AlertStore()


ALERTS = _build_alert_store()
