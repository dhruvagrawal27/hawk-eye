"""Online inference topology — wiring (BACKEND-13, blueprint Part 18.1).

Kafka(events) → Flink enrich+window → Redis/Feast → **L1 rules gateway** → model-serving(L2+L3) →
**L6 fusion** → Kafka(alerts) + ClickHouse. This is the testable Python reference of the Rust hot
path (``backend/gateway/``): the production hot path is Rust; this orchestrates the same stages so
the worked-burst, short-circuit, idempotency, and degradation tests run without Kafka/Flink.

Invariants:
* **Idempotent** — a replayed ``event_id`` never double-alerts (BACKEND-14).
* **L1 short-circuit** — a hard rule hit emits a HIGH alert immediately, skipping ML (BACKEND-11).
* **Graceful degradation** — model server down ⇒ L1-rules-only + mark for re-score, never dark (BACKEND-15).
* **Alert-only** — emits alerts; never blocks money, never classifies. Disposition is human.
"""

from __future__ import annotations

import hashlib

from app.clients.feature_client import FEATURE_READER, FeatureReader
from app.clients.serving_client import SERVING_CLIENT, ServingClient
from app.observability.metrics import ALERTS_EMITTED, RULE_HITS
from app.schemas.alerts import Alert, ReasonCode
from app.schemas.common import iso_z, new_alert_id, utcnow
from app.store.alert_store import ALERTS, AlertStore
from app.store.subthreshold_store import SUBTHRESHOLD
from app.workflow.escalation import apply_sla
from fusion.service import DEFAULT_FUSION, FusionService, build_breakdown
from reliability.circuit_breaker import CircuitBreaker
from reliability.degradation import DEGRADATION
from reliability.idempotency import DEDUPE
from rules_engine.engine import DEFAULT_ENGINE, EvalResult, RulesEngine

EMIT_THRESHOLD = 70  # only surface triage-worthy alerts; lower scores are recorded, not alerted


class OnlinePipeline:
    def __init__(
        self,
        engine: RulesEngine = DEFAULT_ENGINE,
        feature_reader: FeatureReader = FEATURE_READER,
        serving: ServingClient = SERVING_CLIENT,
        fusion: FusionService = DEFAULT_FUSION,
        store: AlertStore = ALERTS,
        *,
        short_circuit: bool = True,
        emit_threshold: int = EMIT_THRESHOLD,
    ):
        self.engine = engine
        self.feature_reader = feature_reader
        self.serving = serving
        self.fusion = fusion
        self.store = store
        self.short_circuit = short_circuit
        self.emit_threshold = emit_threshold
        self.breaker = CircuitBreaker(failure_threshold=3, reset_timeout=5.0)

    # --- public entry points ---
    def process(
        self,
        event: dict,
        *,
        alert_id: str | None = None,
        created_ts: str | None = None,
        full: bool = False,
        force_degraded: bool = False,
    ) -> Alert | None:
        """Process one L0 event. Returns the emitted Alert, or None (deduped / below threshold)."""
        eid = event.get("event_id", "")
        if eid and not DEDUPE.mark(eid):
            return None  # replay → exactly-once: no double alert

        features = self.feature_reader.read(event)
        result = self.engine.evaluate(event, features)
        for code in result.fired_codes:
            RULE_HITS.inc(rule=code)
        graph_ev, ring_id = self._graph_evidence(event, features)

        if self.short_circuit and not full and result.hard_hit:
            return self._emit_short_circuit(event, result, graph_ev, ring_id, alert_id, created_ts)
        return self._emit_fused(
            event, result, features, graph_ev, ring_id, alert_id, created_ts, force_degraded
        )

    def process_full(self, event: dict, **kw) -> Alert | None:
        """Always run serving + L6 fusion (no short-circuit) — used by the demo/seed and tests."""
        return self.process(event, full=True, **kw)

    # --- internal stages ---
    def _score(self, features: dict, routing_key: str, force_degraded: bool):
        if force_degraded or not self.breaker.allow():
            DEGRADATION.enter_degraded()
            return None
        try:
            res = self.breaker.call(self.serving.score, features, routing_key=routing_key)
        except Exception:
            DEGRADATION.enter_degraded()
            return None
        if DEGRADATION.degraded:
            DEGRADATION.recover()
        return res

    def _emit_short_circuit(self, event, result, graph_ev, ring_id, alert_id, created_ts) -> Alert:
        """L1 hard-hit short-circuit: emit HIGH immediately, skip ML (BACKEND-11)."""
        reason_codes = result.reason_codes + [{"source": "graph", "detail": ev} for ev in graph_ev]
        layers = ["L1_rules"] + (["L5_graph"] if graph_ev else [])
        risk = max(85, int(round(result.l1_score * 100)))
        confidence = round(min(0.95, 0.6 + 0.35 * result.l1_score), 2)
        # No ML runs on the short-circuit; the breakdown is rule-driven (L1 + optional L5 graph proxy).
        layer_scores = {"L1_rule": round(result.l1_score, 4)}
        if graph_ev:
            layer_scores["L5_graph"] = 1.0
        breakdown = build_breakdown(
            layer_scores, risk / 100.0, hard_hit=True, confidence=confidence
        )
        return self._emit(
            event,
            risk_score=risk,
            severity="high",
            confidence=confidence,
            contributing_layers=layers,
            reason_codes=reason_codes,
            model_versions={},  # no ML invoked on the short-circuit path
            ring_id=ring_id,
            alert_id=alert_id,
            created_ts=created_ts,
            path="l1_shortcircuit",
            fusion_breakdown=breakdown,
        )

    def _emit_fused(
        self,
        event,
        result: EvalResult,
        features,
        graph_ev,
        ring_id,
        alert_id,
        created_ts,
        force_degraded,
    ) -> Alert | None:
        score_result = self._score(features, event.get("event_id", ""), force_degraded)

        if score_result is None:
            # Graceful degradation: L1 rules only, mark for re-score, never go dark.
            DEGRADATION.mark_for_rescore(event.get("event_id", ""))
            if not result.fired:
                return None
            reason_codes = result.reason_codes + [
                {"source": "graph", "detail": e} for e in graph_ev
            ]
            layers = ["L1_rules"] + (["L5_graph"] if graph_ev else [])
            risk = max(1, int(round(result.l1_score * 100)))
            confidence = round(min(0.9, 0.5 + 0.3 * result.l1_score), 2)
            # Degraded: ML server unavailable — the breakdown honestly shows only the rule floor.
            layer_scores = {"L1_rule": round(result.l1_score, 4)}
            if graph_ev:
                layer_scores["L5_graph"] = 1.0
            breakdown = build_breakdown(
                layer_scores, risk / 100.0, hard_hit=result.hard_hit, confidence=confidence
            )
            return self._emit(
                event,
                risk_score=risk,
                severity=result.severity,
                confidence=confidence,
                contributing_layers=layers,
                reason_codes=reason_codes,
                model_versions={"degraded": "L1_rules_only"},
                ring_id=ring_id,
                alert_id=alert_id,
                created_ts=created_ts,
                path="degraded_l1",
                fusion_breakdown=breakdown,
            )

        fusion = self.fusion.fuse(
            scores=score_result.scores,
            model_versions=score_result.model_versions,
            features=features,
            l1_score=result.l1_score,
            l1_hard_hit=result.hard_hit,
            l1_reason_codes=result.reason_codes,
            graph_evidence=graph_ev,
        )
        emit = (
            result.hard_hit or fusion.severity == "high" or fusion.risk_score >= self.emit_threshold
        )
        # Ambient/sub-threshold capture (the 'hidden 95%'): record EVERY fully-scored event — whether
        # or not it clears the bar — so the detection funnel + near-miss watchlist reflect reality.
        try:
            top = fusion.reason_codes[0] if fusion.reason_codes else {}
            SUBTHRESHOLD.observe(
                entity_id=(event.get("actor") or {}).get("employee_id", "EMP-unknown"),
                score=fusion.risk_score,
                top_signal=str(
                    top.get("code") or top.get("feature") or top.get("detail") or "scored"
                ),
                ts=created_ts or iso_z(utcnow()),
                emitted=bool(emit),
            )
        except Exception:  # pragma: no cover - ambient capture is best-effort, never blocks scoring
            pass
        if not emit:
            return None  # recorded to ClickHouse, not surfaced as an alert
        return self._emit(
            event,
            risk_score=fusion.risk_score,
            severity=fusion.severity,
            confidence=fusion.confidence,
            contributing_layers=fusion.contributing_layers,
            reason_codes=fusion.reason_codes,
            model_versions=fusion.model_versions,
            ring_id=ring_id,
            alert_id=alert_id,
            created_ts=created_ts,
            path="l6_fusion",
            fusion_breakdown=fusion.breakdown,
        )

    def _emit(
        self,
        event,
        *,
        risk_score,
        severity,
        confidence,
        contributing_layers,
        reason_codes,
        model_versions,
        ring_id,
        alert_id,
        created_ts,
        path,
        fusion_breakdown=None,
    ) -> Alert:
        entity = (event.get("actor") or {}).get("employee_id", "EMP-unknown")
        exposure = int((event.get("object") or {}).get("amount") or 0)
        alert = Alert(
            alert_id=alert_id or new_alert_id(),
            entity_id=entity,
            risk_score=risk_score,
            severity=severity,
            confidence=confidence,
            status="open",
            created_ts=created_ts or iso_z(utcnow()),
            contributing_layers=contributing_layers,
            reason_codes=[ReasonCode(**rc) for rc in reason_codes],
            exposure_inr=exposure,
            pii_tokenized=True,
        )
        alert.model_versions = model_versions
        alert.ring_id = ring_id
        alert.fusion_breakdown = fusion_breakdown or {}
        apply_sla(alert)
        self.store.add(alert)
        ALERTS_EMITTED.inc(severity=str(severity), path=path)
        return alert

    def _graph_evidence(self, event, features) -> tuple[list[str], str | None]:
        """Async L5 graph proxy: surface an isolated maker-checker pair as a ring (Part 18.1)."""
        actor = (event.get("actor") or {}).get("employee_id", "")
        if features.get("maker_checker_same_actor"):
            return ([f"{actor} acted as both maker and checker (collusion / self-dealing)"], None)
        if features.get("maker_checker_pair_isolated"):
            partner = features.get("maker_checker_partner", "<partner>")
            ring = _ring_for(actor, partner)
            return (
                [f"maker {actor} + checker {partner} recur as an isolated pair (ring {ring})"],
                ring,
            )
        return ([], None)


def _ring_for(a: str, b: str) -> str:
    h = hashlib.sha256("".join(sorted((a, b))).encode()).hexdigest()
    return f"RNG-{int(h, 16) % 90 + 10}"  # deterministic RNG-10..99


ONLINE = OnlinePipeline()
