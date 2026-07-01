"""WebSocket endpoint ``/ws/alerts`` (mounted at root, outside /api/v1) + a small REST control surface.

The frontend's WsRealtimeSource connects to ``/ws/alerts`` and receives event.scored / alert.new
frames. The REST control (under /api/v1/stream) lets the Replay Studio drive the inprocess generator.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.stream.engine import STREAM

ws_router = APIRouter(tags=["stream"])
stream_router = APIRouter(prefix="/stream", tags=["stream"])


@ws_router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket) -> None:
    await STREAM.connect(ws)
    try:
        while True:
            # The client isn't expected to send; this keeps the socket open while the engine
            # broadcasts. A disconnect surfaces as WebSocketDisconnect.
            await ws.receive_text()
    except WebSocketDisconnect:
        await STREAM.disconnect(ws)
    except Exception:  # noqa: BLE001 - any socket error → clean up the connection
        await STREAM.disconnect(ws)


@stream_router.get("/status")
def stream_status() -> dict:
    return STREAM.status()


@stream_router.post("/inject")
def stream_inject() -> dict:
    """Inject a high-risk burst into the live stream (Replay Studio control)."""
    STREAM.inject_burst()
    return STREAM.status()
