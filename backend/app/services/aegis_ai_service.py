"""
AEGIS AI — in-app product support + educational trading knowledge.

Does not place trades. Not personalized investment advice.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import AiChatMessage

# Curated knowledge: (keywords, answer). Higher keyword hits win.
_KB: list[tuple[list[str], str]] = [
    (
        ["ohlc", "feed", "mq5", "metatrader", "data"],
        "AEGIS_OHLC_Feed.mq5 sends broker OHLC (and equity when configured) to the AEGIS server. "
        "Attach it on MT5 (chart-only or MultiSymbol). Set ServerUrl, AccountId, ApiKey. "
        "Allow WebRequest for your API host under Tools → Options → Expert Advisors.",
    ),
    (
        ["executor", "order", "pending", "batch"],
        "AEGIS_Executor polls /api/executor/pending-batch and places BUY/SELL when the server "
        "publishes a signal. Use MultiPair mode with the same AccountId/ApiKey as the Feed. "
        "One position per symbol is the safe default. Local file signals are only a fallback.",
    ),
    (
        ["api key", "account id", "login", "credentials"],
        "Get Account ID + API key from the LeverageFx portal after demo signup or paid activation "
        "(Connect mobile / credentials reveal). Enter both in the mobile app Settings and in the MT5 EAs. "
        "Do not share your API key.",
    ),
    (
        ["demo", "trial", "free"],
        "Demo signup on the website creates a DEMO account for trial use. Paid plans (Starter/Pro/Business) "
        "unlock commercial entitlements. Autonomous real-money trading stays separately gated by server safety flags.",
    ),
    (
        ["risk", "tolerance", "equity", "percent", "%"],
        "In app Settings, set equity risk tolerance (e.g. 0.5%–50%). The server sizes exposure from equity, "
        "broker min lots, and plan caps — clients do not type raw lot size. MultiSymbol spreads risk across pairs "
        "within that budget when signals allow.",
    ),
    (
        ["hold", "confidence", "threshold"],
        "HOLD means no actionable BUY/SELL: often low confidence, waiting for OHLC, rejected instrument, "
        "or production not authorized. Entry/flip uses a minimum confidence (around 0.75). "
        "Already-open positions reject duplicate same-side signals.",
    ),
    (
        ["multi", "symbol", "pairs", "multipair"],
        "MultiSymbol Feed streams several symbols; MultiPair Executor executes per-symbol signals on one account. "
        "Same AccountId/ApiKey. Prefer an explicit SymbolsList rather than an uncontrolled Market Watch dump.",
    ),
    (
        ["notification", "alert", "bell", "telegram", "email", "sms", "whatsapp"],
        "Signals and fills appear in the in-app notification center (bell). Optional external alerts use "
        "Alert Channels (email, Telegram, SMS, WhatsApp) when configured on the server and in the app. "
        "Billing reminders also land in the inbox near period end.",
    ),
    (
        ["subscription", "billing", "renew", "paystack", "stripe"],
        "Plans: Demo, Starter, Pro, Business (Enterprise is sales-assisted). Payment webhooks activate the plan. "
        "Failed renewal → past_due with a grace period, then suspended. Renew on the website to restore access.",
    ),
    (
        ["community", "chat", "display name", "online"],
        "Community has topic rooms (General, Setup, Markets, Risk, Multi-Pair, etc.). Choose a unique display name. "
        "Online list shows recent presence. AEGIS AI chat is separate product support — not peer chat.",
    ),
    (
        ["screenshot", "camera", "vision", "v48"],
        "AEGIS V48 prioritizes broker-direct OHLC via MT5 Feed for decisions. Screenshots are optional context. "
        "Phone = command/monitor; MT5 = market data & execution; AEGIS server = intelligence.",
    ),
    (
        ["rulebook", "router", "registry"],
        "Each instrument maps through the registry/router to a qualified rulebook path when eligible. "
        "Rejected pairs fail closed (no trade). Research eligibility is not the same as production authorization.",
    ),
    (
        ["what is forex", "foreign exchange", "currency pair"],
        "Forex is trading one currency against another (e.g. EURUSD = euros vs US dollars). "
        "Prices move on interest rates, growth, risk sentiment, and liquidity. "
        "This is education only — not a recommendation to trade any pair.",
    ),
    (
        ["pip", "point", "lot", "mini lot", "micro"],
        "A pip is a small price increment (often 0.0001 on many FX pairs; JPY pairs differ). "
        "Lot size scales profit/loss: standard 1.0, mini 0.10, micro 0.01 (broker-dependent). "
        "AEGIS respects broker minimum volume and your plan/risk caps.",
    ),
    (
        ["spread", "commission", "swap"],
        "Spread is the gap between bid and ask — a trading cost. Some accounts also charge commission. "
        "Swap/rollover is overnight financing. Wide spread can block execution when MaxSpread is set on the Executor.",
    ),
    (
        ["leverage", "margin"],
        "Leverage lets you control larger notional with less margin, which amplifies gains and losses. "
        "Margin is capital reserved for open positions. High leverage increases risk of rapid drawdown. "
        "Never risk money you cannot afford to lose.",
    ),
    (
        ["support", "resistance", "structure"],
        "Support is an area where price often stopped falling; resistance where it often stopped rising. "
        "Market structure (higher highs/lows or lower highs/lows) helps describe trend vs range. "
        "Educational concepts only — AEGIS rulebooks encode specific tested conditions per pair.",
    ),
    (
        ["trend", "ranging", "sideways", "regime"],
        "Trending markets show directional structure; ranging markets oscillate between bounds. "
        "Strategies that work in one regime can fail in another. Risk controls and fail-closed routing "
        "exist because no single pattern works in all conditions.",
    ),
    (
        ["volatility", "atr", "news"],
        "Volatility is how large moves are. ATR is a common average-range measure. "
        "High-impact news can gap prices and widen spreads — dangerous for tight stops. "
        "Consider reducing risk around major releases; this is general education, not a signal.",
    ),
    (
        ["stop loss", "take profit", "sl", "tp"],
        "Stop loss limits loss if price moves against you; take profit banks a target. "
        "AEGIS may use strategy SL points and/or confidence-based flips instead of fixed TP. "
        "Always verify protective levels on the MT5 position after a fill.",
    ),
    (
        ["drawdown", "risk management", "position size"],
        "Drawdown is decline from peak equity. Position size should fit a predefined risk fraction of equity. "
        "AEGIS risk tolerance % and MultiSymbol portfolio logic aim to keep aggregate exposure inside your setting. "
        "Past performance does not guarantee future results.",
    ),
    (
        ["overtrading", "revenge", "discipline"],
        "Overtrading and revenge trading after a loss are common failure modes. "
        "Automated rules and daily trade caps exist to reduce impulsive decisions. "
        "You remain responsible for account funding, broker choice, and enabling EAs.",
    ),
    (
        ["backtest", "forward test", "demo first"],
        "Historical tests can overfit. Prefer walk-forward style validation and demo/live-small size before scaling. "
        "AEGIS rulebooks are research-qualified under internal gates; still treat live capital carefully.",
    ),
    (
        ["candlestick", "ohlc", "open high low close"],
        "Each candle summarizes Open, High, Low, Close for a timeframe (e.g. M5). "
        "AEGIS feature engines use OHLC history from MT5, not guessed pixel prices from screenshots.",
    ),
    (
        ["timeframe", "m5", "h1", "multi timeframe"],
        "Timeframe is the bar size (M5 = 5 minutes). Higher timeframes filter noise; lower ones react faster. "
        "AEGIS pair rulebooks are typically aligned to a specific timeframe (often M5 in current research paths).",
    ),
    (
        ["correlation", "diversification"],
        "Correlated pairs (e.g. some USD pairs) can move together — several positions may be one bet in disguise. "
        "Diversification across less-correlated symbols can reduce concentrated risk but does not eliminate loss.",
    ),
    (
        ["slippage", "requote", "filling"],
        "Slippage is fill price differing from request. Requotes occur when price moves before fill. "
        "Executor uses adaptive filling modes where possible; some brokers reject certain fill policies.",
    ),
    (
        ["vps", "latency", "24/7"],
        "A VPS keeps MT5 Feed + Executor online without your PC. Lower, stable latency to the broker helps. "
        "Phone monitoring can be intermittent; server + MT5 should keep running if EAs are hosted on VPS.",
    ),
]


class AegisAiService:
    async def history(self, account_id: str, limit: int = 50) -> list[dict[str, Any]]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AiChatMessage)
                .where(AiChatMessage.account_id == account_id)
                .order_by(AiChatMessage.created_at.desc())
                .limit(limit)
            )
            rows = list(reversed(result.scalars().all()))
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
                "AEGIS AI is product support and general education only. "
                "It does not place trades or provide personalized investment advice."
            ),
        }

    def _answer(self, question: str) -> str:
        q = question.lower()
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
                "\n\nTip: ask about Feed, Executor, risk %, HOLD, billing, or trading basics "
                "(pips, margin, volatility). Educational answers are not personal advice."
            )
        return (
            "I am AEGIS AI — product support and trading education for LeverageFx / AEGIS.\n\n"
            "I can help with: OHLC Feed, Executor, API keys, risk tolerance, HOLD reasons, "
            "multi-pair mode, billing, and basics (pips, margin, spreads, structure, risk).\n\n"
            "Ask something specific (e.g. \"What is spread?\" or \"How do I set MultiSymbol?\"). "
            "I never execute trades from this chat."
        )
