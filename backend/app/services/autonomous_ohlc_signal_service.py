"""
Autonomous MultiSymbol signals from MT5 OHLC stream (not mobile dropdown).

On each CLOSED bar ingest:
  OHLC Feed → evaluate rulebook → confidence gate → Executor publish

Confidence policy (default EXEC_MIN_CONFIDENCE=0.75):
  - Open / flip only when signal confidence >= threshold
  - Same direction while already in that direction → reject (hold)
  - Opposite direction below threshold → reject (keep position; no fixed TP)
  - Opposite direction at/above threshold → publish flip (Executor closes + reverses)

Mobile app symbol selection is NOT required for this path.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger("AEGIS.autonomous_ohlc")


class AutonomousOhlcSignalService:
    def __init__(self) -> None:
        # account_id|SYMBOL -> last committed side BUY|SELL
        self._side: dict[str, str] = {}

    def _key(self, account_id: str, symbol: str) -> str:
        return f"{account_id}|{(symbol or '').upper().split('.')[0]}"

    def get_side(self, account_id: str, symbol: str) -> str | None:
        return self._side.get(self._key(account_id, symbol))

    def set_side(self, account_id: str, symbol: str, side: str | None) -> None:
        k = self._key(account_id, symbol)
        if side in ("BUY", "SELL"):
            self._side[k] = side
        elif k in self._side:
            del self._side[k]

    def min_confidence(self) -> float:
        try:
            return float(getattr(settings, "EXEC_MIN_CONFIDENCE", 0.75) or 0.75)
        except Exception:
            return 0.75

    def gate_signal(
        self,
        account_id: str,
        symbol: str,
        side: str,
        confidence: float,
    ) -> tuple[bool, str]:
        """Return (allow_publish, reason)."""
        side_u = (side or "").upper()
        if side_u not in ("BUY", "SELL"):
            return False, "not_actionable"
        thr = self.min_confidence()
        conf = float(confidence or 0.0)
        if conf < thr:
            return False, f"confidence_below_threshold:{conf:.2f}<{thr:.2f}"
        current = self.get_side(account_id, symbol)
        if current == side_u:
            return False, f"same_direction_open:{current}"
        if current is None:
            return True, "open_new"
        # opposite → flip
        return True, f"flip_{current}_to_{side_u}"

    async def process_closed_bar(
        self,
        *,
        app: Any,
        account_id: str,
        symbol: str,
        timeframe: str,
        stream_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate one symbol from OHLC stream and optionally publish to Executor."""
        out: dict[str, Any] = {
            "account_id": account_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "published": False,
        }
        if not account_id or not symbol:
            out["reason"] = "missing_account_or_symbol"
            return out

        from app.services.universal_analysis_service import UniversalAnalysisService

        # Build snapshot for evaluators
        closed = stream_payload.get("closed_bar") or {}
        bars = stream_payload.get("bars") or []
        snapshot: dict[str, Any] = {
            "close": closed.get("close") if isinstance(closed, dict) else stream_payload.get("close"),
            "open": closed.get("open") if isinstance(closed, dict) else None,
            "high": closed.get("high") if isinstance(closed, dict) else None,
            "low": closed.get("low") if isinstance(closed, dict) else None,
            "time": closed.get("time") if isinstance(closed, dict) else None,
            "bars": bars,
            "source": "mt5_ohlc_stream",
            "bar_status": "CLOSED",
        }
        if snapshot["close"] is None and bars:
            try:
                last = bars[-1]
                snapshot["close"] = last.get("close")
                snapshot["open"] = last.get("open")
                snapshot["high"] = last.get("high")
                snapshot["low"] = last.get("low")
            except Exception:
                pass

        uni = UniversalAnalysisService()
        result = uni.analyze(
            instrument=symbol.strip().upper().split(".")[0],
            timeframe=(timeframe or "M5").strip() or "M5",
            market_snapshot=snapshot,
            frame_state=None,
        )
        side = str(result.get("signal") or "HOLD").upper()
        conf = float(result.get("confidence") or 0.0)
        out["signal"] = side
        out["confidence"] = conf
        out["rule_name"] = result.get("rule_name")
        out["router_state"] = result.get("router_state")

        allow, reason = self.gate_signal(account_id, symbol, side, conf)
        out["gate"] = reason
        if not allow:
            out["reason"] = reason
            return out

        # Registry / risk / publish (shared with screenshot path intent)
        exec_svc = getattr(app.state, "executor_signals", None) or getattr(
            app.state, "executor_signal_service", None
        )
        if exec_svc is None:
            out["reason"] = "executor_service_unavailable"
            return out

        sym = symbol.strip().upper().split(".")[0]
        # Hard-reject check
        reg = getattr(app.state, "registry_service", None) or getattr(app.state, "registry", None)
        if reg is not None:
            try:
                rows = reg.list_instruments(tradeable_only=False)
                m = next(
                    (
                        r
                        for r in rows
                        if str(r.get("instrument") or "").upper() == sym
                    ),
                    None,
                )
                if m is not None:
                    rs = str(m.get("router_status") or "").upper()
                    if rs in {
                        "TRADING_DISABLED",
                        "DISABLED",
                        "REJECTED",
                        "TRANSFER_REJECTED",
                    }:
                        out["reason"] = f"rejected:{rs}"
                        return out
            except Exception as e:
                out["registry_error"] = str(e)

        sized_vol = 0.01
        try:
            pr = getattr(app.state, "portfolio_risk", None)
            plan_code = "demo"
            sub_svc = getattr(app.state, "subscription_service", None)
            if sub_svc is not None:
                try:
                    st = await sub_svc.get_status(account_id)
                    if isinstance(st, dict):
                        plan_code = (st.get("plan") or "demo").lower()
                except Exception:
                    pass
            if pr is not None:
                risk_meta = await pr.size_order(account_id, sym, plan_code)
                out["portfolio_risk"] = risk_meta
                if not risk_meta.get("allow"):
                    out["reason"] = risk_meta.get("reason") or "risk_blocked"
                    return out
                sized_vol = float(risk_meta.get("volume") or 0.01)
        except Exception as e:
            out["risk_error"] = str(e)

        # SL/TP optional — primary exit is opposite high-confidence signal
        sl = result.get("stop_loss") or result.get("sl")
        tp = result.get("take_profit") or result.get("tp")
        # Prefer no fixed TP when using confidence-flip exits
        tp = None
        try:
            px = float(snapshot.get("close") or 0)
        except Exception:
            px = 0.0
        if px > 0 and not sl:
            sl = px * (0.995 if side == "BUY" else 1.005)

        try:
            exec_svc.publish(
                account_id=account_id,
                symbol=sym,
                side=side,
                confidence=conf,
                rule_name=str(result.get("rule_name") or ""),
                volume=sized_vol,
                stop_loss=float(sl) if sl else None,
                take_profit=None,  # confidence-flip exit model
                details=f"autonomous_ohlc gate={reason} conf={conf:.2f}"[:500],
            )
            self.set_side(account_id, sym, side)
            out["published"] = True
            out["reason"] = reason
            out["volume"] = sized_vol
            # Inbox notification (non-blocking)
            try:
                notif = getattr(app.state, "notifications", None)
                if notif is not None:
                    await notif.create(
                        account_id=account_id,
                        type="signal",
                        title=f"{side} {sym}",
                        message=f"Autonomous OHLC signal {side} conf={conf:.0%} ({reason})",
                        severity="info",
                        pair=sym,
                        signal=side,
                        confidence=conf,
                        rule_name=str(result.get("rule_name") or ""),
                        deliver_external=True,
                    )
            except Exception:
                pass
        except Exception as e:
            out["reason"] = f"publish_error:{e}"
            logger.exception("publish failed")

        return out
