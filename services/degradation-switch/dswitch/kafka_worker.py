"""Optional Kafka worker for the degradation switch (PLATFORM-4).

When ENABLE_KAFKA_WORKER=true and Kafka is reachable, runs the real topology hop:
  consume hawkeye.events.l0 -> score (current mode) -> produce hawkeye.alerts
  (+ hawkeye.rescore when an event was scored rules-only, so nothing is dropped).

Runs in a daemon thread started at app startup. If confluent-kafka is missing or the
broker is unreachable it logs and exits the thread — the HTTP /score endpoint still
works, so the switch is testable without a running cluster.
"""
from __future__ import annotations

import json
import logging
import os
import threading

from . import health, scoring

log = logging.getLogger("degradation-switch.kafka")

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
IN_TOPIC = "hawkeye.events.l0"
ALERTS_TOPIC = "hawkeye.alerts"
RESCORE_TOPIC = "hawkeye.rescore"
_started = False


def _run() -> None:
    try:
        from confluent_kafka import Consumer, Producer
    except Exception as e:  # pragma: no cover
        log.warning("confluent-kafka unavailable (%s); Kafka worker disabled", e)
        return
    try:
        consumer = Consumer({
            "bootstrap.servers": BOOTSTRAP,
            "group.id": "degradation-switch",
            "auto.offset.reset": "latest",
        })
        producer = Producer({"bootstrap.servers": BOOTSTRAP})
        consumer.subscribe([IN_TOPIC])
        log.info("Kafka worker consuming %s -> %s", IN_TOPIC, ALERTS_TOPIC)
    except Exception as e:  # pragma: no cover
        log.warning("Kafka unreachable (%s); worker disabled", e)
        return

    while True:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        try:
            ev = json.loads(msg.value())
            mode = health.current_mode()
            layer_scores = None  # full-mode worker could enrich from serving here
            alert = scoring.score_event(ev, mode, layer_scores)
            if alert:
                producer.produce(ALERTS_TOPIC, json.dumps(alert).encode())
                if alert.get("marked_for_rescore"):
                    producer.produce(RESCORE_TOPIC, msg.value())
                producer.poll(0)
        except Exception as e:  # never let one bad event kill the loop (Part 32.2)
            log.error("scoring error: %s", e)


def start() -> None:
    global _started
    if _started or os.environ.get("ENABLE_KAFKA_WORKER", "false").lower() != "true":
        return
    _started = True
    threading.Thread(target=_run, name="degradation-kafka-worker", daemon=True).start()
