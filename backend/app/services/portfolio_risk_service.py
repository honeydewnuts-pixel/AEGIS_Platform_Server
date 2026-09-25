"""
Equity-aware portfolio risk for MultiSymbol and chart-only modes.

Client sets:
  - account equity (USD)
  - max risk tolerance % of equity: 5,10,...,45
  - trading mode: multi_symbol | chart_only

Server:
  - risk_budget = equity * tolerance_pct / 100
  - per-symbol min notional / min lot from table or defaults
  - max concurrent pairs = min(24, floor(budget / min_notional)) when multi_symbol
  - lot size scaled within plan max_lot and remaining budget
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

    async def max_pairs_for_account(self, account_id: str) -> int:
        state = await self.get_state(account_id)
        if not state or not state.get("account_equity_usd"):
            return 1
        budget = float(state["risk_budget_usd"] or 0)
        if budget <= 0:
            return 0
        # Use median default min notional for capacity estimate
        avg_min = DEFAULT_MIN_NOTIONAL_USD
        n = int(budget // avg_min)
        return max(0, min(MAX_MULTISYMBOL_PAIRS, n if n > 0 else 0))

    async def size_order(
        self,
        account_id: str,
        symbol: str,
        plan_code: str,
        *,
        active_open_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Decide whether a new/ongoing signal for `symbol` may trade and at what lot.

        Returns:
          allow, volume, reason, risk_allocation_usd, max_pairs, ...
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
            # No equity reported yet — fall back to plan lot, single-pair safe path
            max_lot = get_max_lot(plan_code)
            return {
                "allow": True,
                "volume": float(max_lot if max_lot <= 0.01 else 0.01),
                "reason": "equity_not_set_fallback_min_lot",
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

        max_pairs = await self.max_pairs_for_account(account_id)
        if mode == "multi_symbol":
            if not already_open and len(active) >= max_pairs:
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "max_pairs_reached",
                    "max_pairs": max_pairs,
                    "active_pairs": len(active),
                }
            if not already_open and remaining < min_notional:
                # Micro / small equity: still allow one min_lot if equity is positive
                # and remaining covers a fraction of min_notional (cent-account safe).
                equity_f = float(equity or 0)
                if equity_f >= 5.0 and remaining >= max(1.0, min_notional * 0.05):
                    return {
                        "allow": True,
                        "volume": float(min_lot),
                        "reason": "micro_min_lot_fallback",
                        "remaining_risk_usd": remaining,
                        "min_notional_usd": min_notional,
                        "min_lot": min_lot,
                    }
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "insufficient_remaining_risk",
                    "remaining_risk_usd": remaining,
                    "min_notional_usd": min_notional,
                }
        else:
            # chart_only: only the selected symbol; still respect remaining budget
            if remaining < min_notional and not already_open:
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "insufficient_remaining_risk",
                    "remaining_risk_usd": remaining,
                }

        plan_max = float(get_max_lot(plan_code))
        # Equal-weight remaining risk budget across free MultiSymbol slots
        free_slots = max(1, max_pairs - len(active) + (1 if already_open else 0))
        slot_budget = remaining / free_slots if free_slots else remaining

        # Primary: treat slot_budget as *margin* available for this pair under assumed leverage.
        # notional ≈ margin * leverage; lots ≈ notional / 100k (FX-style).
        # Example: equity $10k, 25% → $2500 budget, 11 pairs → ~$227/slot
        #          * 100 lev → ~$22.7k notional → ~0.23 lots (not 0.01).
        margin_per_standard_lot = STANDARD_LOT_NOTIONAL_USD / max(1.0, ASSUMED_ACCOUNT_LEVERAGE)
        if margin_per_standard_lot > 0:
            raw_lots = slot_budget / margin_per_standard_lot
        else:
            raw_lots = min_lot

        # Floor: at least enough to open min_lot if budget covers min_notional margin
        if raw_lots < min_lot and slot_budget >= max(0.5, min_notional * 0.05):
            raw_lots = min_lot

        volume = max(min_lot, min(plan_max, round(raw_lots, 2)))
        if volume < min_lot:
            volume = min_lot
        if volume > plan_max:
            volume = plan_max

        # Estimated margin reserved for this open (for open_risk tracking)
        allocation = round(volume * margin_per_standard_lot, 2)

        return {
            "allow": True,
            "volume": float(volume),
            "reason": "ok",
            "risk_allocation_usd": allocation,
            "slot_budget_usd": round(slot_budget, 2),
            "assumed_leverage": ASSUMED_ACCOUNT_LEVERAGE,
            "min_notional_usd": min_notional,
            "min_lot": min_lot,
            "max_pairs": max_pairs,
            "risk_budget_usd": budget,
            "remaining_risk_usd": remaining,
            "trading_mode": mode,
            "plan_max_lot": plan_max,
        }

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
