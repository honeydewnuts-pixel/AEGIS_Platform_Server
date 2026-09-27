"""
Equity-aware portfolio risk for MultiSymbol and chart-only modes.

Client sets:
  - account equity (USD)
  - max risk tolerance % of equity: 5,10,...,45
  - trading mode: multi_symbol | chart_only

Server:
  - risk_budget = equity * tolerance_pct / 100
  - position size = stop-loss risk budget / loss-per-lot (position_sizing_engine)
  - margin check is separate from stop-loss risk sizing
  - max concurrent pairs from budget capacity when multi_symbol
  - halt when drawdown from peak exceeds risk budget (tolerance of equity)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.base import async_session_factory
from app.db.models import InstrumentMinNotional, Subscription
from app.services.plan_catalog import get_max_lot, resolve_plan

ALLOWED_TOLERANCE_PCT = (0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
MAX_MULTISYMBOL_PAIRS = 24
DEFAULT_MIN_NOTIONAL_USD = 10.0
DEFAULT_MIN_LOT = 0.01
# Used to convert risk-slot USD into lots when broker min_notional is only a floor.
# volume ≈ (slot_budget_usd * leverage) / 100_000  for FX-style notionals.
ASSUMED_ACCOUNT_LEVERAGE = 100.0
STANDARD_LOT_NOTIONAL_USD = 100_000.0

# Conservative default min notionals (USD) when broker has not reported
DEFAULT_SYMBOL_MIN_NOTIONAL: dict[str, float] = {
    # Micro-friendly defaults: Feed may overwrite with broker SymbolInfo
    "EURUSD": 10, "GBPUSD": 10, "USDJPY": 10, "USDCHF": 10, "AUDUSD": 10,
    "NZDUSD": 10, "USDCAD": 10, "EURGBP": 10, "EURCHF": 10, "EURJPY": 10,
    "GBPJPY": 10, "GBPNZD": 10, "NZDCHF": 10, "NZDJPY": 10, "AUDNZD": 10,
    "XAUUSD": 50, "XAGUSD": 25, "BTCUSD": 50, "ETHUSD": 25,
}


class PortfolioRiskService:
    def __init__(self) -> None:
        pass

    async def get_state(self, account_id: str) -> dict[str, Any] | None:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                return None
            equity = float(row.account_equity_usd) if row.account_equity_usd is not None else None
            peak = float(row.peak_equity_usd) if row.peak_equity_usd is not None else equity
            pct = float(row.risk_tolerance_pct if row.risk_tolerance_pct is not None else 25.0)
            budget = (equity * pct / 100.0) if equity and equity > 0 else 0.0
            open_risk = float(row.open_risk_usd or 0.0)
            remaining = max(0.0, budget - open_risk)
            return {
                "account_id": account_id,
                "account_equity_usd": equity,
                "peak_equity_usd": peak,
                "risk_tolerance_pct": pct,
                "risk_budget_usd": round(budget, 2),
                "open_risk_usd": round(open_risk, 2),
                "remaining_risk_usd": round(remaining, 2),
                "trading_mode": row.trading_mode or "multi_symbol",
                "trading_halted": bool(row.trading_halted),
                "halted_reason": row.halted_reason,
                "plan": row.plan,
            }

    async def set_equity(self, account_id: str, equity_usd: float, source: str = "client") -> dict[str, Any]:
        if equity_usd < 0:
            raise ValueError("equity must be >= 0")
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            prev = float(row.account_equity_usd) if row.account_equity_usd is not None else None
            row.account_equity_usd = float(equity_usd)
            peak = float(row.peak_equity_usd) if row.peak_equity_usd is not None else 0.0
            if equity_usd > peak:
                row.peak_equity_usd = float(equity_usd)
            # Auto-resume if client adds capital and was halted for risk
            if row.trading_halted and equity_usd > (prev or 0):
                pct = float(row.risk_tolerance_pct if row.risk_tolerance_pct is not None else 25.0)
                peak = float(row.peak_equity_usd or equity_usd)
                dd = max(0.0, peak - equity_usd)
                budget = equity_usd * pct / 100.0
                if dd < budget:
                    row.trading_halted = False
                    row.halted_reason = None
            await session.commit()
        return await self.evaluate_halt(account_id)

    async def set_risk_tolerance_pct(self, account_id: str, pct: float) -> dict[str, Any]:
        try:
            val = float(pct)
        except (TypeError, ValueError) as e:
            raise ValueError(f"risk_tolerance_pct must be one of {ALLOWED_TOLERANCE_PCT}") from e
        if val not in ALLOWED_TOLERANCE_PCT:
            raise ValueError(f"risk_tolerance_pct must be one of {ALLOWED_TOLERANCE_PCT}")
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            row.risk_tolerance_pct = val
            # Changing tolerance may clear halt if drawdown now within budget
            await session.commit()
        return await self.evaluate_halt(account_id)

    async def set_trading_mode(self, account_id: str, mode: str) -> dict[str, Any]:
        mode = (mode or "").strip().lower()
        if mode not in ("multi_symbol", "chart_only"):
            raise ValueError("trading_mode must be multi_symbol or chart_only")
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            row.trading_mode = mode
            await session.commit()
        return await self.get_state(account_id)  # type: ignore

    async def evaluate_halt(self, account_id: str) -> dict[str, Any]:
        """Halt if drawdown from peak equity exceeds risk budget."""
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            equity = float(row.account_equity_usd) if row.account_equity_usd is not None else None
            if equity is None or equity <= 0:
                state = await self.get_state(account_id)
                return state  # type: ignore
            peak = float(row.peak_equity_usd) if row.peak_equity_usd is not None else equity
            if equity > peak:
                row.peak_equity_usd = equity
                peak = equity
            pct = float(row.risk_tolerance_pct if row.risk_tolerance_pct is not None else 25.0)
            budget = equity * pct / 100.0
            dd = max(0.0, peak - equity)
            if dd >= budget and budget > 0:
                row.trading_halted = True
                row.halted_reason = (
                    f"Drawdown ${dd:.2f} reached risk tolerance "
                    f"({pct}% of equity = ${budget:.2f}). "
                    "Deposit more equity or lower risk tolerance to resume."
                )
            await session.commit()
        return await self.get_state(account_id)  # type: ignore

    async def get_min_notional(self, symbol: str) -> tuple[float, float]:
        base = symbol.upper().split(".")[0]
        async with async_session_factory() as session:
            row = await session.get(InstrumentMinNotional, base)
            if row is not None:
                return float(row.min_notional_usd), float(row.min_lot)
        return (
            float(DEFAULT_SYMBOL_MIN_NOTIONAL.get(base, DEFAULT_MIN_NOTIONAL_USD)),
            DEFAULT_MIN_LOT,
        )

    async def upsert_min_notional(
        self, symbol: str, min_notional_usd: float, min_lot: float = 0.01
    ) -> None:
        base = symbol.upper().split(".")[0]
        async with async_session_factory() as session:
            row = await session.get(InstrumentMinNotional, base)
            now = datetime.now(timezone.utc)
            if row is None:
                session.add(
                    InstrumentMinNotional(
                        symbol=base,
                        min_notional_usd=float(min_notional_usd),
                        min_lot=float(min_lot),
                        updated_at=now,
                    )
                )
            else:
                row.min_notional_usd = float(min_notional_usd)
                row.min_lot = float(min_lot)
                row.updated_at = now
            await session.commit()

    async def max_pairs_for_account(self, account_id: str, symbol: str | None = None) -> int:
        """
        How many concurrent pairs the risk budget can unlock.

        risk_budget = equity * tolerance_pct / 100
        capacity ≈ floor(budget / broker_min_notional) capped at 24

        When `symbol` is provided, that instrument's min_notional (broker-reported
        or default) is used so unlock count tracks real tradable dollar size.
        """
        state = await self.get_state(account_id)
        if not state or not state.get("account_equity_usd"):
            return 1
        budget = float(state["risk_budget_usd"] or 0)
        if budget <= 0:
            return 0
        if symbol:
            unit, _ = await self.get_min_notional(symbol)
        else:
            # Conservative capacity: use larger of default and typical FX floor
            unit = float(DEFAULT_MIN_NOTIONAL_USD)
        unit = max(1.0, float(unit))
        n = int(budget // unit)
        return max(0, min(MAX_MULTISYMBOL_PAIRS, n))

    async def size_order(
        self,
        account_id: str,
        symbol: str,
        plan_code: str,
        *,
        active_open_symbols: list[str] | None = None,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        side: str | None = None,
        available_margin: float | None = None,
        margin_per_lot: float | None = None,
        account_currency: str = "USD",
        fx_rates: dict[str, float] | None = None,
        instrument_spec: Any = None,
        atr14: float | None = None,
    ) -> dict[str, Any]:
        """
        1) AEGIS assesses per-trade risk % from client tolerance + portfolio state.
        2) Size by stop-loss: volume = (equity * assessed_risk%) / loss_per_lot.

        Client configures risk *tolerance* only — not a fixed per-trade %.
        """
        state = await self.get_state(account_id)
        if state is None:
            return {"allow": False, "volume": 0.0, "reason": "account_not_found"}

        if state.get("trading_halted"):
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "trading_halted",
                "halted_reason": state.get("halted_reason"),
            }

        equity = state.get("account_equity_usd")
        if equity is None or float(equity) <= 0:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "equity_required_for_risk_sizing",
                "risk_budget_usd": 0,
            }

        min_notional, min_lot = await self.get_min_notional(symbol)
        budget = float(state["risk_budget_usd"])
        open_risk = float(state["open_risk_usd"])
        remaining = max(0.0, budget - open_risk)
        mode = state.get("trading_mode") or "multi_symbol"
        active = [s.upper().split(".")[0] for s in (active_open_symbols or [])]
        sym = symbol.upper().split(".")[0]
        already_open = sym in active
        pct = float(state.get("risk_tolerance_pct") or 25.0)

        max_pairs = await self.max_pairs_for_account(account_id, symbol=sym)
        if mode == "multi_symbol":
            if not already_open and len(active) >= max_pairs:
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "max_pairs_reached",
                    "max_pairs": max_pairs,
                    "active_pairs": len(active),
                }
        else:
            if remaining <= 0 and not already_open:
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "insufficient_remaining_risk",
                    "remaining_risk_usd": remaining,
                }

        side_u = (side or "").upper()
        if side_u not in ("BUY", "SELL"):
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "side_required_for_stop_risk_sizing",
                "risk_budget_usd": budget,
                "client_risk_tolerance_pct": pct,
            }
        if entry_price is None or float(entry_price) <= 0:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "entry_price_required_for_stop_risk_sizing",
                "risk_budget_usd": budget,
                "client_risk_tolerance_pct": pct,
            }
        if stop_loss is None:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "stop_loss_required",
                "risk_budget_usd": budget,
                "client_risk_tolerance_pct": pct,
            }

        # Stop distance for assessment (price units)
        ep = float(entry_price)
        slp = float(stop_loss)
        if side_u == "SELL":
            stop_dist = slp - ep
        else:
            stop_dist = ep - slp

        peak = state.get("peak_equity_usd")
        assessment = assess_per_trade_risk(
            client_tolerance_pct=pct,
            equity=float(equity),
            open_risk_usd=open_risk,
            peak_equity=float(peak) if peak is not None else float(equity),
            max_concurrent_slots=max_pairs if mode == "multi_symbol" else 1,
            open_positions=len(active),
            stop_distance=stop_dist if stop_dist > 0 else None,
            atr14=float(atr14) if atr14 is not None else None,
            trading_halted=bool(state.get("trading_halted")),
        )
        if not assessment.allow:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": assessment.reason,
                "client_risk_tolerance_pct": pct,
                "aegis_per_trade_risk_pct": 0.0,
                "risk_assessment": assessment.to_dict(),
                "risk_budget_usd": budget,
                "sizing_method": "aegis_assessed_stop_risk",
            }

        per_trade_pct = float(assessment.per_trade_risk_pct)
        # Monetary budget for THIS trade from assessed % (not full client tolerance)
        trade_budget = float(equity) * per_trade_pct / 100.0
        # Still cannot exceed remaining portfolio tolerance capacity
        trade_budget = min(trade_budget, remaining)

        spec = instrument_spec or default_spec_for_symbol(sym)
        if spec is None:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "instrument_spec_unavailable",
                "symbol": sym,
                "client_risk_tolerance_pct": pct,
                "aegis_per_trade_risk_pct": per_trade_pct,
            }

        if min_lot and min_lot > 0:
            from dataclasses import replace
            step = getattr(spec, "volume_step", min_lot) or min_lot
            spec = replace(spec, volume_min=float(min_lot), volume_step=float(step))

        rates = dict(fx_rates or {})
        rates.update(fx_rates_for_pair_price(sym, ep))

        plan_max = float(get_max_lot(plan_code))
        result = size_by_stop_risk(
            equity=float(equity),
            risk_pct=per_trade_pct,
            entry_price=ep,
            stop_loss=slp,
            side=side_u,  # type: ignore[arg-type]
            spec=spec,
            account_currency=account_currency,
            fx_rates=rates,
            open_risk_usd=0.0,
            risk_budget_override=trade_budget,
            available_margin=available_margin,
            margin_per_lot=margin_per_lot,
            plan_max_volume=plan_max,
        )
        out = result.to_dict()
        out["max_pairs"] = max_pairs
        out["risk_budget_usd"] = budget
        out["trade_risk_budget_usd"] = trade_budget
        out["client_risk_tolerance_pct"] = pct
        out["aegis_per_trade_risk_pct"] = per_trade_pct
        out["risk_assessment"] = assessment.to_dict()
        out["trading_mode"] = mode
        out["plan_max_lot"] = plan_max
        out["min_notional_usd"] = min_notional
        out["risk_allocation_usd"] = float(out.get("estimated_monetary_risk") or 0.0)
        out["sizing_method"] = "aegis_assessed_stop_risk"
        return out

    async def record_open_risk(self, account_id: str, delta_usd: float) -> None:
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                return
            row.open_risk_usd = max(0.0, float(row.open_risk_usd or 0.0) + float(delta_usd))
            await session.commit()

    async def portfolio_summary(self, account_id: str, universe: list[str] | None = None) -> dict[str, Any]:
        state = await self.get_state(account_id)
        if not state:
            return {"error": "account_not_found"}
        max_pairs = await self.max_pairs_for_account(account_id)
        pairs = universe or list(DEFAULT_SYMBOL_MIN_NOTIONAL.keys())[:MAX_MULTISYMBOL_PAIRS]
        return {
            **state,
            "max_concurrent_pairs": max_pairs,
            "universe_size": len(pairs),
            "allowed_tolerance_pct": list(ALLOWED_TOLERANCE_PCT),
            "note": (
                "In multi_symbol mode clients do not pick pairs; AEGIS allocates "
                "up to max_concurrent_pairs from live signals within risk budget."
            ),
        }
