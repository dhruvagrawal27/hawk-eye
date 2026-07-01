"""WebSocket connection manager — one fan-out point for the realtime stream."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks connected sockets and broadcasts a JSON message to all of them, reaping dead ones."""

    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._conns)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._conns.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._conns.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._conns):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - a dead socket should never break the broadcast
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.discard(ws)
