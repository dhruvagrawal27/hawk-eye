"""Bi-directional SIEM integration (BACKEND-27, blueprint Part 9.3).

Consume SIEM logs as a source (normalize to L0-shaped events) and publish alerts as a sink.
SCAFFOLD: the connector is production-shaped but binds to the bank's live SIEM (Splunk/QRadar/
Sentinel) which is absent locally — it runs against synthetic fixtures. Augment-don't-replace: the
SIEM remains a log source and an alert sink; Hawk-Eye is the unifying brain (Part 3.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SiemConnector:
    """Bi-directional SIEM adapter (consume logs / publish alerts)."""

    source_name: str = "bank-siem"
    published: list[dict] = field(default_factory=list)
    live: bool = False  # SCAFFOLD: True only when wired to the live SIEM (PLATFORM gateway)

    def consume_logs(self, raw_logs: list[dict]) -> list[dict]:
        """Normalize raw SIEM log rows into L0-shaped events (DATA owns the canonical schema)."""
        events: list[dict] = []
        for row in raw_logs:
            events.append(
                {
                    "event_id": row.get("id", f"siem_{len(events)}"),
                    "ts": row.get("timestamp"),
                    "actor": {
                        "employee_id": row.get("user", "EMP-unknown"),
                        "privileged_flag": bool(row.get("privileged")),
                    },
                    "action": {"verb": row.get("action", "siem_event"), "channel": "siem"},
                    "object": {},
                    "context": {
                        "src_ip": row.get("src_ip"),
                        "device": row.get("host"),
                        "layer": "siem",
                        "is_off_hours": bool(row.get("off_hours")),
                    },
                    "linkage": {},
                }
            )
        return events

    def publish_alert(self, alert: dict) -> dict:
        """Publish an alert back to the SIEM as a sink (scaffolded; recorded locally)."""
        envelope = {
            "source": "hawk-eye",
            "type": "insider_fraud_alert",
            "alert_id": alert.get("alert_id"),
            "severity": alert.get("severity"),
            "risk_score": alert.get("risk_score"),
            "entity_id": alert.get("entity_id"),
            "delivered": self.live,  # False under SCAFFOLD — recorded, not delivered
        }
        self.published.append(envelope)
        return envelope


SIEM = SiemConnector()
