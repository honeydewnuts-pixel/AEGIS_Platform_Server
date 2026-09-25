"""In-process WebSocket fan-out for community rooms and DMs."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class CommunityWsHub:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # key -> set of websockets
        self._room: dict[str, set[WebSocket]] = {}
        self._dm: dict[str, set[WebSocket]] = {}
        self._account: dict[str, set[WebSocket]] = {}

    async def connect(self, ws: WebSocket, account_id: str) -> None:
        await ws.accept()
        async with self._lock:
            self._account.setdefault(account_id, set()).add(ws)

    async def disconnect(self, ws: WebSocket, account_id: str) -> None:
        async with self._lock:
            for bucket in (self._room, self._dm, self._account):
                for key, socks in list(bucket.items()):
                    socks.discard(ws)
                    if not socks:
                        bucket.pop(key, None)

    async def join_room(self, ws: WebSocket, room_id: str) -> None:
        async with self._lock:
            self._room.setdefault(room_id, set()).add(ws)

    async def join_dm(self, ws: WebSocket, thread_id: str) -> None:
        async with self._lock:
            self._dm.setdefault(thread_id, set()).add(ws)

    async def broadcast_room(self, room_id: str, payload: dict[str, Any]) -> None:
        await self._send(self._room.get(room_id, set()), payload)

    async def broadcast_dm(self, thread_id: str, payload: dict[str, Any]) -> None:
        await self._send(self._dm.get(thread_id, set()), payload)

    async def notify_account(self, account_id: str, payload: dict[str, Any]) -> None:
        await self._send(self._account.get(account_id, set()), payload)

    async def _send(self, socks: set[WebSocket], payload: dict[str, Any]) -> None:
        data = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in list(socks):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            socks.discard(ws)
