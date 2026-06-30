"""Realtime stream (BACKEND-13 online topology made live).

Exposes a WebSocket ``/ws/alerts`` that broadcasts ``event.scored`` / ``alert.new`` messages the
frontend's WsRealtimeSource already speaks. Two modes (config ``HAWKEYE_STREAM_MODE``):
``inprocess`` (an asyncio replay loop scores synthetic events through ONLINE and broadcasts — no
brokers, demonstrable anywhere) and ``kafka`` (consume the events topic, score, bridge through Redis
pub/sub, fan out to WS — the production path).
"""
