"""Peer community chat — display names, presence, rooms. Isolated from trading."""

from __future__ import annotations

import re
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import ChatMessage, ChatRoom, ChatReport, CommunityProfile, DmMessage, DmThread

MAX_BODY = 2000
RATE_WINDOW_SEC = 60
RATE_MAX = 30
ONLINE_WINDOW_SEC = 90
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,23}$")
RESERVED_NAMES = frozenset(
    {
        "admin",
        "administrator",
        "aegis",
        "aegisai",
        "aegis_ai",
        "system",
        "moderator",
        "mod",
        "support",
        "official",
        "leveragefx",
        "honeydewnuts",
        "staff",
        "root",
        "null",
        "undefined",
    }
)
_BLOCK = re.compile(
    r"(api[_-]?key\s*[:=]|password\s*[:=]|private\s*key|sk_live|Bearer\s+[A-Za-z0-9_\-]{20,})",
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
    def default_display_name(account_id: str) -> str:
        aid = (account_id or "").strip()
        if len(aid) <= 8:
            return f"Trader_{aid}"
        return f"Trader_{aid[-6:]}"

    @classmethod
    def validate_display_name(cls, name: str) -> str:
        raw = (name or "").strip()
        if not NAME_RE.match(raw):
            raise ValueError(
                "display_name must be 3–24 chars, start with a letter, "
                "and use only letters, numbers, underscore"
            )
        if raw.lower() in RESERVED_NAMES:
            raise ValueError("display_name is reserved")
        if raw.lower().startswith("trader_") and len(raw) <= 12:
            # allow auto names; custom names should not look like system
            pass
        return raw

    async def get_profile(self, account_id: str) -> dict[str, Any]:
        async with async_session_factory() as session:
            row = await session.get(CommunityProfile, account_id)
            if row is None:
                return {
                    "account_id": account_id,
                    "display_name": self.default_display_name(account_id),
                    "display_name_set": False,
                    "last_seen_at": None,
                    "online": False,
                }
            online = False
            if row.last_seen_at:
                online = (
                    datetime.now(timezone.utc) - row.last_seen_at
                ) <= timedelta(seconds=ONLINE_WINDOW_SEC)
            return {
                "account_id": account_id,
                "display_name": row.display_name,
                "display_name_set": True,
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
                "online": online,
            }

    async def set_display_name(self, account_id: str, display_name: str) -> dict[str, Any]:
        name = self.validate_display_name(display_name)
        lower = name.lower()
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            # uniqueness
            taken = (
                await session.execute(
                    select(CommunityProfile).where(
                        CommunityProfile.display_name_lower == lower,
                        CommunityProfile.account_id != account_id,
                    )
                )
            ).scalar_one_or_none()
            if taken is not None:
                raise ValueError("display_name_taken")
            row = await session.get(CommunityProfile, account_id)
            if row is None:
                row = CommunityProfile(
                    account_id=account_id,
                    display_name=name,
                    display_name_lower=lower,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.display_name = name
                row.display_name_lower = lower
                row.updated_at = now
                row.last_seen_at = now
            await session.commit()
        return await self.get_profile(account_id)

    async def heartbeat(self, account_id: str) -> dict[str, Any]:
        """Mark user online; create profile with default name if missing."""
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            row = await session.get(CommunityProfile, account_id)
            if row is None:
                base = self.default_display_name(account_id)
                # ensure unique default
                candidate = base
                n = 0
                while True:
                    exists = (
                        await session.execute(
                            select(CommunityProfile).where(
                                CommunityProfile.display_name_lower == candidate.lower()
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is None:
                        break
                    n += 1
                    candidate = f"{base}_{n}"
                row = CommunityProfile(
                    account_id=account_id,
                    display_name=candidate,
                    display_name_lower=candidate.lower(),
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.last_seen_at = now
            await session.commit()
        return await self.get_profile(account_id)

    async def list_online(self, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ONLINE_WINDOW_SEC)
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(CommunityProfile)
                    .where(CommunityProfile.last_seen_at >= cutoff)
                    .order_by(CommunityProfile.last_seen_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
            return [
                {
                    "display_name": r.display_name,
                    "last_seen_at": r.last_seen_at.isoformat() if r.last_seen_at else None,
                }
                for r in rows
            ]

    async def _resolve_name(self, session, account_id: str) -> str:
        row = await session.get(CommunityProfile, account_id)
        if row is not None:
            return row.display_name
        return self.default_display_name(account_id)

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

    async def _resolve_room_id(self, session, room_id: str) -> str:
        room = await session.get(ChatRoom, room_id)
        if room is not None:
            return room.id
        r = (
            await session.execute(select(ChatRoom).where(ChatRoom.slug == room_id))
        ).scalar_one_or_none()
        if r is None:
            raise ValueError("room_not_found")
        return r.id

    async def list_messages(
        self,
        room_id: str,
        *,
        limit: int = 50,
        before_id: int | None = None,
        after_id: int | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        async with async_session_factory() as session:
            rid = await self._resolve_room_id(session, room_id)
            q = select(ChatMessage).where(
                ChatMessage.room_id == rid,
                ChatMessage.deleted.is_(False),
            )
            if after_id:
                q = q.where(ChatMessage.id > after_id).order_by(ChatMessage.id.asc()).limit(limit)
                rows = list((await session.execute(q)).scalars().all())
            else:
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
                    "attachment_url": getattr(m, "attachment_url", None),
                    "attachment_mime": getattr(m, "attachment_mime", None),
                    "created_at": m.created_at.isoformat(),
                }
                for m in rows
            ]


    async def open_dm(self, account_id: str, peer_display_name: str) -> dict[str, Any]:
        """Open or return DM thread by peer display name."""
        peer = (peer_display_name or "").strip()
        if not peer:
            raise ValueError("peer_required")
        async with async_session_factory() as session:
            peer_row = (
                await session.execute(
                    select(CommunityProfile).where(
                        CommunityProfile.display_name_lower == peer.lower()
                    )
                )
            ).scalar_one_or_none()
            if peer_row is None:
                raise ValueError("peer_not_found")
            peer_id = peer_row.account_id
            if peer_id == account_id:
                raise ValueError("cannot_dm_self")
            a, b = sorted([account_id, peer_id])
            existing = (
                await session.execute(
                    select(DmThread).where(
                        DmThread.account_a == a, DmThread.account_b == b
                    )
                )
            ).scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if existing:
                return {
                    "thread_id": existing.id,
                    "peer_display_name": peer_row.display_name,
                    "peer_account_suffix": peer_id[-4:],
                }
            tid = "dm-" + hashlib.sha256(f"{a}:{b}".encode()).hexdigest()[:16]
            session.add(
                DmThread(
                    id=tid,
                    account_a=a,
                    account_b=b,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            return {
                "thread_id": tid,
                "peer_display_name": peer_row.display_name,
                "peer_account_suffix": peer_id[-4:],
            }

    async def list_dm_threads(self, account_id: str) -> list[dict[str, Any]]:
        async with async_session_factory() as session:
            rows = (
                await session.execute(
                    select(DmThread).where(
                        (DmThread.account_a == account_id)
                        | (DmThread.account_b == account_id)
                    ).order_by(DmThread.updated_at.desc())
                )
            ).scalars().all()
            out = []
            for th in rows:
                peer_id = th.account_b if th.account_a == account_id else th.account_a
                peer = await session.get(CommunityProfile, peer_id)
                name = peer.display_name if peer else self.default_display_name(peer_id)
                out.append(
                    {
                        "thread_id": th.id,
                        "peer_display_name": name,
                        "updated_at": th.updated_at.isoformat(),
                    }
                )
            return out

    async def list_dm_messages(
        self, thread_id: str, account_id: str, *, limit: int = 50, after_id: int | None = None
    ) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        async with async_session_factory() as session:
            th = await session.get(DmThread, thread_id)
            if th is None or account_id not in (th.account_a, th.account_b):
                raise ValueError("thread_forbidden")
            q = select(DmMessage).where(
                DmMessage.thread_id == thread_id, DmMessage.deleted.is_(False)
            )
            if after_id:
                q = q.where(DmMessage.id > after_id).order_by(DmMessage.id.asc()).limit(limit)
                rows = list((await session.execute(q)).scalars().all())
            else:
                q = q.order_by(DmMessage.id.desc()).limit(limit)
                rows = list((await session.execute(q)).scalars().all())
                rows.reverse()
            return [
                {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "display_name": m.display_name,
                    "body": m.body,
                    "attachment_url": m.attachment_url,
                    "attachment_mime": m.attachment_mime,
                    "created_at": m.created_at.isoformat(),
                    "mine": m.sender_id == account_id,
                }
                for m in rows
            ]

    async def post_dm(
        self,
        thread_id: str,
        account_id: str,
        body: str,
        *,
        attachment_url: str | None = None,
        attachment_mime: str | None = None,
    ) -> dict[str, Any]:
        if not self._rate_ok(account_id):
            raise ValueError("rate_limited")
        text = (body or "").strip()
        if not text and not attachment_url:
            raise ValueError("empty_message")
        if len(text) > MAX_BODY:
            raise ValueError("message_too_long")
        if text and _BLOCK.search(text):
            raise ValueError("message_blocked_sensitive")
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            th = await session.get(DmThread, thread_id)
            if th is None or account_id not in (th.account_a, th.account_b):
                raise ValueError("thread_forbidden")
            name = await self._resolve_name(session, account_id)
            prof = await session.get(CommunityProfile, account_id)
            if prof is not None:
                prof.last_seen_at = now
            th.updated_at = now
            msg = DmMessage(
                thread_id=thread_id,
                sender_id=account_id,
                display_name=name,
                body=text or "[image]",
                attachment_url=attachment_url,
                attachment_mime=attachment_mime,
                created_at=now,
                deleted=False,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return {
                "id": msg.id,
                "thread_id": msg.thread_id,
                "display_name": msg.display_name,
                "body": msg.body,
                "attachment_url": msg.attachment_url,
                "attachment_mime": msg.attachment_mime,
                "created_at": msg.created_at.isoformat(),
            }

    async def post_message(
        self,
        room_id: str,
        account_id: str,
        body: str,
        *,
        attachment_url: str | None = None,
        attachment_mime: str | None = None,
    ) -> dict[str, Any]:
        if not self._rate_ok(account_id):
            raise ValueError("rate_limited")
        text = (body or "").strip()
        if not text and not attachment_url:
            raise ValueError("empty_message")
        if len(text) > MAX_BODY:
            raise ValueError("message_too_long")
        if text and _BLOCK.search(text):
            raise ValueError("message_blocked_sensitive")
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            rid = await self._resolve_room_id(session, room_id)
            name = await self._resolve_name(session, account_id)
            prof = await session.get(CommunityProfile, account_id)
            if prof is not None:
                prof.last_seen_at = now
            msg = ChatMessage(
                room_id=rid,
                account_id=account_id,
                display_name=name,
                body=text or "[image]",
                attachment_url=attachment_url,
                attachment_mime=attachment_mime,
                created_at=now,
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
                "attachment_url": msg.attachment_url,
                "attachment_mime": msg.attachment_mime,
                "created_at": msg.created_at.isoformat(),
            }

    async def report_message(
        self,
        reporter_id: str,
        *,
        target_type: str,
        target_message_id: int,
        reason: str,
        room_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        reason_s = (reason or "").strip()[:512]
        if len(reason_s) < 3:
            raise ValueError("reason_required")
        tt = (target_type or "").lower()
        if tt not in ("room", "dm"):
            raise ValueError("invalid_target_type")
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            if tt == "room":
                m = await session.get(ChatMessage, target_message_id)
                if m is None:
                    raise ValueError("message_not_found")
                room_id = m.room_id
            else:
                m = await session.get(DmMessage, target_message_id)
                if m is None:
                    raise ValueError("message_not_found")
                thread_id = m.thread_id
            rep = ChatReport(
                reporter_id=reporter_id,
                target_type=tt,
                target_message_id=target_message_id,
                room_id=room_id,
                thread_id=thread_id,
                reason=reason_s,
                status="open",
                created_at=now,
            )
            session.add(rep)
            await session.commit()
            await session.refresh(rep)
            return {"id": rep.id, "status": rep.status}

    async def list_reports(self, *, status: str = "open", limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(200, limit))
        async with async_session_factory() as session:
            q = select(ChatReport).order_by(ChatReport.id.desc()).limit(limit)
            if status and status != "all":
                q = select(ChatReport).where(ChatReport.status == status).order_by(
                    ChatReport.id.desc()
                ).limit(limit)
            rows = (await session.execute(q)).scalars().all()
            return [
                {
                    "id": r.id,
                    "reporter_id_suffix": (r.reporter_id or "")[-6:],
                    "target_type": r.target_type,
                    "target_message_id": r.target_message_id,
                    "room_id": r.room_id,
                    "thread_id": r.thread_id,
                    "reason": r.reason,
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]

    async def resolve_report(
        self, report_id: int, *, status: str, note: str = ""
    ) -> dict[str, Any]:
        st = (status or "").lower()
        if st not in ("reviewed", "dismissed", "actioned"):
            raise ValueError("invalid_status")
        async with async_session_factory() as session:
            r = await session.get(ChatReport, report_id)
            if r is None:
                raise ValueError("report_not_found")
            r.status = st
            r.resolved_at = datetime.now(timezone.utc)
            r.resolver_note = (note or "")[:512]
            if st == "actioned" and r.target_type == "room":
                m = await session.get(ChatMessage, r.target_message_id)
                if m:
                    m.deleted = True
            if st == "actioned" and r.target_type == "dm":
                m = await session.get(DmMessage, r.target_message_id)
                if m:
                    m.deleted = True
            await session.commit()
            return {"id": r.id, "status": r.status}

    async def soft_delete_room_message(self, message_id: int) -> bool:
        async with async_session_factory() as session:
            m = await session.get(ChatMessage, message_id)
            if m is None:
                return False
            m.deleted = True
            await session.commit()
            return True
