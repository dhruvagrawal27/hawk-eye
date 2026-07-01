"""Stream engine — drives the live broadcast in either inprocess or kafka mode.

inprocess: an asyncio loop generates synthetic L0 events, scores them through ONLINE, and broadcasts
           event.scored / alert.new to all WS clients. Runs only while ≥1 client is connected.
kafka:     a consumer reads the events topic, scores, and publishes results to a Redis pub/sub channel;
           a Redis subscriber in each API worker fans the channel out to its WS clients (multi-worker
           correct). Imports aiokafka/redis lazily and falls back to inprocess if brokers are unavailable.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from app.config import settings
from app.pipeline.online import ONLINE
from app.store.score_history import SCORE_HISTORY
from app.stream.generator import alert_json, make_event, make_tick
from app.stream.manager import ConnectionManager

log = logging.getLogger("hawkeye.stream")


class StreamEngine:
    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self._inproc: asyncio.Task | None = None
        self._kafka_tasks: list[asyncio.Task] = []
        self._burst = 0
        self.events = 0
        self.alerts = 0
        self._effective_mode = settings.stream_mode

    # ---- WS lifecycle (called by ws_routes) ----
    async def connect(self, ws) -> None:
        await self.manager.connect(ws)
        if self._effective_mode == "inprocess":
            self._ensure_inprocess()

    async def disconnect(self, ws) -> None:
        await self.manager.disconnect(ws)
        if self.manager.count == 0 and self._inproc is not None:
            self._inproc.cancel()
            self._inproc = None

    def inject_burst(self, n: int = 8) -> None:
        self._burst += n
        if self._effective_mode == "inprocess":
            self._ensure_inprocess()

    def status(self) -> dict:
        return {
            "mode": self._effective_mode,
            "configured_mode": settings.stream_mode,
            "clients": self.manager.count,
            "events_published": self.events,
            "alerts_fired": self.alerts,
            "running": self._inproc is not None or bool(self._kafka_tasks),
        }

    # ---- inprocess loop ----
    def _ensure_inprocess(self) -> None:
        if self._inproc is None or self._inproc.done():
            self._burst = max(self._burst, 10)  # front-load a mule burst
            self._inproc = asyncio.create_task(self._inprocess_loop())

    async def _score_and_broadcast(self, event: dict) -> None:
        try:
            alert = ONLINE.process(event, full=True)
        except Exception:  # noqa: BLE001 - scoring must never kill the stream
            alert = None
        self.events += 1
        tick = make_tick(event, alert)
        # persist the scored point to the score-history store (ClickHouse when enabled, else memory)
        try:
            SCORE_HISTORY.record(
                tick["employee_id"], tick["ts"], int(tick["score"]),
                event_id=str(event.get("event_id", "")), note=str(tick.get("top_signal") or ""),
            )
        except Exception:  # noqa: BLE001
            pass
        await self.manager.broadcast(tick)
        if alert is not None:
            self.alerts += 1
            await self.manager.broadcast({"type": "alert.new", "alert": alert_json(alert)})

    async def _inprocess_loop(self) -> None:
        # Floor 0.005s ⇒ up to ~200 eps; default rate is 50 eps (HAWKEYE_STREAM_RATE). The base delay
        # is jittered per tick so the live EPS reads as a natural rate (~45–55 around 50) rather than
        # a suspicious flat 50.0.
        import random

        base = max(0.005, 1.0 / max(0.5, settings.stream_rate))
        try:
            while self.manager.count > 0:
                hot = self._burst > 0
                if hot:
                    self._burst -= 1
                await self._score_and_broadcast(make_event(hot))
                await asyncio.sleep(max(0.005, base * random.uniform(0.83, 1.22)))
        except asyncio.CancelledError:
            pass

    # ---- kafka/redis production path (started/stopped by the app lifespan) ----
    async def start_kafka(self) -> None:
        try:
            from aiokafka import AIOKafkaConsumer  # type: ignore
            import redis.asyncio as aioredis  # type: ignore
        except Exception as exc:  # noqa: BLE001
            log.warning("kafka mode requested but aiokafka/redis unavailable (%s); using inprocess", exc)
            self._effective_mode = "inprocess"
            return

        try:
            consumer = AIOKafkaConsumer(
                settings.kafka_events_topic,
                bootstrap_servers=settings.kafka_bootstrap,
                group_id="hawkeye-scorer",
                value_deserializer=lambda b: json.loads(b.decode()),
                auto_offset_reset="latest",
            )
            redis = aioredis.from_url(settings.redis_url)
            await consumer.start()
        except Exception as exc:  # noqa: BLE001 - brokers down → degrade to inprocess, never dark
            log.warning("kafka/redis start failed (%s); falling back to inprocess", exc)
            self._effective_mode = "inprocess"
            return

        self._effective_mode = "kafka"
        self._kafka_tasks = [
            asyncio.create_task(self._kafka_consume(consumer, redis)),
            asyncio.create_task(self._redis_subscribe(redis)),
        ]
        log.info("kafka stream started: topic=%s redis=%s", settings.kafka_events_topic, settings.redis_url)

    async def _kafka_consume(self, consumer, redis) -> None:
        chan = settings.redis_stream_channel
        try:
            async for msg in consumer:
                event = msg.value
                try:
                    alert = ONLINE.process(event, full=True)
                except Exception:  # noqa: BLE001
                    alert = None
                self.events += 1
                await redis.publish(chan, json.dumps(make_tick(event, alert)))
                if alert is not None:
                    self.alerts += 1
                    await redis.publish(chan, json.dumps({"type": "alert.new", "alert": alert_json(alert)}))
        except asyncio.CancelledError:
            pass
        finally:
            with contextlib.suppress(Exception):
                await consumer.stop()

    async def _redis_subscribe(self, redis) -> None:
        pubsub = redis.pubsub()
        await pubsub.subscribe(settings.redis_stream_channel)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                with contextlib.suppress(Exception):
                    await self.manager.broadcast(json.loads(msg["data"]))
        except asyncio.CancelledError:
            pass
        finally:
            with contextlib.suppress(Exception):
                await pubsub.close()

    async def stop_kafka(self) -> None:
        for t in self._kafka_tasks:
            t.cancel()
        self._kafka_tasks = []


STREAM = StreamEngine()
