"""AEGIS AI assistant — product support chat. Never places trades."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import AiChatMessage

# Curated knowledge (no hype). Expand over time.
_KB: list[tuple[list[str], str]] = [
    (
        ["ohlc", "feed", "mq5", "stream"],
        "Install AEGIS_OHLC_Feed.mq5 on MT5 (VPS or desktop). Set ServerUrl to your AEGIS API, "
        "AccountId + ApiKey, MultiSymbol mode and your SymbolsList. The Feed posts broker OHLC "
        "to /api/mt5/ohlc/stream. Screenshots are optional context; OHLC is authoritative.",
    ),
    (
        ["executor", "order", "trade", "pending"],
        "AEGIS_Executor.mq5 polls /api/executor/pending-batch for BUY/SELL only. HOLD never "
        "opens an order. Use MultiPair, UseServerSignals=true, matching SymbolsList, and the "
        "same AccountId/ApiKey as the Feed. Demo accounts can execute when the server publishes "
        "signals; production live capital stays gated by authorization.",
    ),
    (
        ["demo", "trial", "api key", "account"],
        "Create a free demo from the LeverageFx website. After activation, open the portal "
        "Connect mobile screen for Account ID + API key. Enter those in the mobile app Settings "
        "and in both MT5 EAs. Never share your API key in community chat.",
    ),
    (
        ["risk", "tolerance", "equity", "micro", "lot"],
        "In mobile Settings set equity and risk tolerance (0.5%–50%). AEGIS sizes lots from "
        "equity × tolerance and broker min lot/notional. Micro and small accounts can trade "
        "min lot when risk allows. Demo max lot is typically 0.01.",
    ),
    (
        ["hold", "confidence", "signal"],
        "HOLD means no executable BUY/SELL. Common reasons: waiting for OHLC, confidence below "
        "threshold, rejected instrument, or no matching structure. Check Analysis and HTTP code "
        "on the mobile home screen.",
    ),
    (
        ["pair", "symbol", "multisymbol", "multipair"],
        "MultiSymbol Feed + MultiPair Executor use one account key for many pairs. Each pair "
        "needs its own signal; not all pairs trade at once. Rejected registry instruments stay "
        "fail-closed.",
    ),
    (
        ["notification", "alert", "bell"],
        "The notification bell shows unread count. Open Notifications for signal and system "
        "history. Prefer email/Telegram only after configuring notification preferences securely.",
    ),
]


class AegisAiService:
    def __init__(self) -> None:
        self._external = (os.environ.get("AEGIS_AI_API_URL") or "").strip()

    async def history(self, account_id: str, limit: int = 40) -> list[dict[str, Any]]:
        limit = max(1, min(100, limit))
        async with async_session_factory() as session:
            q = (
                select(AiChatMessage)
                .where(AiChatMessage.account_id == account_id)
                .order_by(AiChatMessage.id.desc())
                .limit(limit)
            )
            rows = list((await session.execute(q)).scalars().all())
            rows.reverse()
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "body": m.body,
                    "created_at": m.created_at.isoformat(),
                }
                for m in rows
            ]

    async def ask(self, account_id: str, question: str) -> dict[str, Any]:
        text = (question or "").strip()
        if not text:
            raise ValueError("empty_message")
        if len(text) > 2000:
            raise ValueError("message_too_long")

        reply = self._answer(text)
        now = datetime.now(timezone.utc)
        async with async_session_factory() as session:
            session.add(
                AiChatMessage(
                    account_id=account_id, role="user", body=text, created_at=now
                )
            )
            session.add(
                AiChatMessage(
                    account_id=account_id, role="assistant", body=reply, created_at=now
                )
            )
            await session.commit()
        return {
            "role": "assistant",
            "body": reply,
            "disclaimer": (
                "AEGIS AI is product support only. It does not place trades or provide "
                "personalized investment advice."
            ),
        }

    def _answer(self, question: str) -> str:
        q = question.lower()
        # Safety: refuse trade-execution commands
        if re.search(r"\b(buy|sell|close all|open trade)\b.+\b(now|for me)\b", q):
            return (
                "I cannot place or close trades from chat. Use MT5 + AEGIS_Executor with "
                "server signals, and risk settings in the app. Trading remains under your control."
            )
        scored: list[tuple[int, str]] = []
        for keys, ans in _KB:
            score = sum(1 for k in keys if k in q)
            if score:
                scored.append((score, ans))
        if scored:
            scored.sort(key=lambda x: -x[0])
            return scored[0][1] + (
                "\n\nNeed a deeper walkthrough? Say whether you are on mobile, MT5 Feed, or Executor."
            )
        return (
            "I am AEGIS AI — product support for LeverageFx / AEGIS.\n\n"
            "I can help with: OHLC Feed setup, Executor, demo API keys, risk tolerance, "
            "HOLD reasons, and multi-pair mode.\n\n"
            "Ask a specific question (e.g. \"How do I set MultiSymbol on the Feed?\"). "
            "I never execute trades from this chat."
        )
