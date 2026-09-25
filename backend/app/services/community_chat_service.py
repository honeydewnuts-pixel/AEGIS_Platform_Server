"""Peer community chat — isolated from trading / execution path."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import ChatMessage, ChatRoom

MAX_BODY = 2000
RATE_WINDOW_SEC = 60
RATE_MAX = 20

# Mild client-side style filter (server-side safety net)
_BLOCK = re.compile(
    r"(api[_-]?key\s*[:=]|password\s*[:=]|private\s*key)",
    re.I,
)

DEFAULT_ROOMS = (
    ("general", "General", "Community chat for AEGIS traders"),
    ("setup", "Setup & VPS", "Feed, Executor, MT5, and install help"),
    ("markets", "Markets", "General market discussion (not financial advice)"),
)


class CommunityChatService:
    def __init__(self) -> None:
        self._recent: dict[str, list[float]] = {}

    async def ensure_default_rooms(self) -> None:
        async with async_session_factory() as session:
            for slug, title, desc in DEFAULT_ROOMS:
                existing = await session.execute(
                    select(ChatRoom).where(ChatRoom.slug == slug)
                )
                if existing.scalar_one_or_none() is None:
                    session.add(
                        ChatRoom(
                            id=f"room-{slug}",
                            slug=slug,
                            title=title,
                            description=desc,
                            is_public=True,
                            created_at=datetime.now(timezone.utc),
                        )
                    )
            await session.commit()

    def _rate_ok(self, account_id: str) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        q = self._recent.setdefault(account_id, [])
        q[:] = [t for t in q if now - t < RATE_WINDOW_SEC]
        if len(q) >= RATE_MAX:
            return False
        q.append(now)
        return True

    @staticmethod
    def _display_name(account_id: str) -> str:
        aid = (account_id or "").strip()
        if len(aid) <= 8:
            return f"Trader-{aid}"
        return f"Trader-{aid[-6:]}"

    async def list_rooms(self) -> list[dict[str, Any]]:
        await self.ensure_default_rooms()
        async with async_session_factory() as session:
            rows = (
                await session.execute(select(ChatRoom).order_by(ChatRoom.slug))
            ).scalars().all()
            return [
                {
                    "id": r.id,
                    "slug": r.slug,
                    "title": r.title,
                    "description": r.description,
                    "is_public": r.is_public,
                }
                for r in rows
            ]

    async def list_messages(
        self, room_id: str, *, limit: int = 50, before_id: int | None = None
    ) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        async with async_session_factory() as session:
            q = select(ChatMessage).where(
                ChatMessage.room_id == room_id,
                ChatMessage.deleted.is_(False),
            )
            if before_id:
                q = q.where(ChatMessage.id < before_id)
            q = q.order_by(ChatMessage.id.desc()).limit(limit)
            rows = list((await session.execute(q)).scalars().all())
            rows.reverse()
            return [
                {
                    "id": m.id,
                    "room_id": m.room_id,
                    "display_name": m.display_name,
                    "body": m.body,
                    "created_at": m.created_at.isoformat(),
                    "mine_hint_account_suffix": (m.account_id or "")[-4:],
                }
                for m in rows
            ]

    async def post_message(
        self, room_id: str, account_id: str, body: str
    ) -> dict[str, Any]:
        if not self._rate_ok(account_id):
            raise ValueError("rate_limited")
        text = (body or "").strip()
        if not text:
            raise ValueError("empty_message")
        if len(text) > MAX_BODY:
            raise ValueError("message_too_long")
        if _BLOCK.search(text):
            raise ValueError("message_blocked_sensitive")
        async with async_session_factory() as session:
            room = await session.get(ChatRoom, room_id)
            if room is None:
                # try slug
                r = (
                    await session.execute(select(ChatRoom).where(ChatRoom.slug == room_id))
                ).scalar_one_or_none()
                if r is None:
                    raise ValueError("room_not_found")
                room_id = r.id
            msg = ChatMessage(
                room_id=room_id,
                account_id=account_id,
                display_name=self._display_name(account_id),
                body=text,
                created_at=datetime.now(timezone.utc),
                deleted=False,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return {
                "id": msg.id,
                "room_id": msg.room_id,
                "display_name": msg.display_name,
                "body": msg.body,
                "created_at": msg.created_at.isoformat(),
            }
