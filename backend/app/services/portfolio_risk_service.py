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
from app.db.models import BrokerInstrumentSpec, InstrumentMinNotional, Subscription
from app.services.plan_catalog import get_max_lot, resolve_plan

ALLOWED_TOLERANCE_PCT = (0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
ALLOWED_ACCOUNT_TYPES = ("standard", "micro", "custom")
MAX_MULTISYMBOL_PAIRS = 24
DEFAULT_MIN_NOTIONAL_USD = 10.0
DEFAULT_MIN_LOT = 0.01
# Fail-closed when last free-margin report is older than this (seconds)
MARGIN_STALE_SECONDS = 600
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
            avail_m = getattr(row, "available_margin_usd", None)
            margin_at = getattr(row, "margin_updated_at", None)
            return {
                "account_id": account_id,
                "account_equity_usd": equity,
                "peak_equity_usd": peak,
                "risk_tolerance_pct": pct,
                "account_type": getattr(row, "account_type", None) or "standard",
                "account_currency": getattr(row, "account_currency", None) or "USD",
                "broker_id": getattr(row, "broker_id", None),
                "available_margin_usd": float(avail_m) if avail_m is not None else None,
                "margin_updated_at": margin_at.isoformat() if margin_at is not None else None,
                "risk_budget_usd": round(budget, 2),
                "open_risk_usd": round(open_risk, 2),
                "remaining_risk_usd": round(remaining, 2),
                "trading_mode": row.trading_mode or "multi_symbol",
                "trading_halted": bool(row.trading_halted),
                "halted_reason": row.halted_reason,
                "plan": row.plan,
            }

    async def set_equity(
        self,
        account_id: str,
        equity_usd: float,
        source: str = "client",
        *,
        available_margin_usd: float | None = None,
    ) -> dict[str, Any]:
        """Persist equity and optional free margin from MT5.

        available_margin_usd must be ACCOUNT_MARGIN_FREE (or equivalent).
        Never pass equity as a substitute for free margin.
        """
        if equity_usd < 0:
            raise ValueError("equity must be >= 0")
        if available_margin_usd is not None and float(available_margin_usd) < 0:
            raise ValueError("available_margin_usd must be >= 0")
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            prev = float(row.account_equity_usd) if row.account_equity_usd is not None else None
            row.account_equity_usd = float(equity_usd)
            peak = float(row.peak_equity_usd) if row.peak_equity_usd is not None else 0.0
            if equity_usd > peak:
                row.peak_equity_usd = float(equity_usd)
            if available_margin_usd is not None:
                row.available_margin_usd = float(available_margin_usd)
                row.margin_updated_at = datetime.now(timezone.utc)
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


    async def set_account_profile(
        self,
        account_id: str,
        *,
        account_type: str | None = None,
        account_currency: str | None = None,
        broker_id: str | None = None,
    ) -> dict[str, Any]:
        """Configure broker account profile (not strategy risk tolerance)."""
        async with async_session_factory() as session:
            row = await session.get(Subscription, account_id)
            if row is None:
                raise ValueError("account not found")
            if account_type is not None:
                at = account_type.strip().lower()
                if at not in ALLOWED_ACCOUNT_TYPES:
                    raise ValueError(f"account_type must be one of {ALLOWED_ACCOUNT_TYPES}")
                row.account_type = at
            if account_currency is not None:
                ccy = account_currency.strip().upper()
                if not ccy or len(ccy) > 16:
                    raise ValueError("invalid account_currency")
                row.account_currency = ccy
            if broker_id is not None:
                row.broker_id = (broker_id.strip() or None)
            await session.commit()
        return await self.get_state(account_id)  # type: ignore

    async def upsert_instrument_spec(
        self,
        symbol: str,
        *,
        account_type: str = "standard",
        broker_id: str = "default",
        contract_size: float,
        volume_min: float,
        volume_max: float,
        volume_step: float,
        tick_size: float,
        tick_value: float | None = None,
        margin_per_lot: float | None = None,
        base_currency: str = "USD",
        quote_currency: str = "USD",
        profit_currency: str | None = None,
        min_notional_usd: float | None = None,
        source: str = "mt5",
    ) -> dict[str, Any]:
        """Store broker/EA instrument specifications for sizing."""
        base = symbol.upper().split(".")[0]
        at = (account_type or "standard").strip().lower()
        if at not in ALLOWED_ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {ALLOWED_ACCOUNT_TYPES}")
        bid = (broker_id or "default").strip() or "default"
        if contract_size <= 0 or volume_min <= 0 or volume_step <= 0 or tick_size <= 0:
            raise ValueError("invalid instrument specification values")
        now = datetime.now(timezone.utc)
        pc = (profit_currency or quote_currency or "USD").upper()
        async with async_session_factory() as session:
            q = await session.execute(
                select(BrokerInstrumentSpec).where(
                    BrokerInstrumentSpec.symbol == base,
                    BrokerInstrumentSpec.account_type == at,
                    BrokerInstrumentSpec.broker_id == bid,
                )
            )
            row = q.scalar_one_or_none()
            if row is None:
                row = BrokerInstrumentSpec(
                    symbol=base,
                    account_type=at,
                    broker_id=bid,
                    contract_size=float(contract_size),
                    volume_min=float(volume_min),
                    volume_max=float(volume_max),
                    volume_step=float(volume_step),
                    tick_size=float(tick_size),
                    tick_value=float(tick_value) if tick_value is not None else None,
                    margin_per_lot=float(margin_per_lot) if margin_per_lot is not None else None,
                    base_currency=base_currency.upper(),
                    quote_currency=quote_currency.upper(),
                    profit_currency=pc,
                    min_notional_usd=float(min_notional_usd) if min_notional_usd is not None else None,
                    source=source[:32],
                    updated_at=now,
                )
                session.add(row)
            else:
                row.contract_size = float(contract_size)
                row.volume_min = float(volume_min)
                row.volume_max = float(volume_max)
                row.volume_step = float(volume_step)
                row.tick_size = float(tick_size)
                row.tick_value = float(tick_value) if tick_value is not None else None
                row.margin_per_lot = float(margin_per_lot) if margin_per_lot is not None else None
                row.base_currency = base_currency.upper()
                row.quote_currency = quote_currency.upper()
                row.profit_currency = pc
                row.min_notional_usd = float(min_notional_usd) if min_notional_usd is not None else None
                row.source = source[:32]
                row.updated_at = now
            # Keep legacy min_notional table in sync for capacity helpers
            mn = await session.get(InstrumentMinNotional, base)
            lot = float(volume_min)
            notion = float(min_notional_usd) if min_notional_usd is not None else float(
                DEFAULT_SYMBOL_MIN_NOTIONAL.get(base, DEFAULT_MIN_NOTIONAL_USD)
            )
            if mn is None:
                session.add(InstrumentMinNotional(symbol=base, min_notional_usd=notion, min_lot=lot, updated_at=now))
            else:
                mn.min_lot = lot
                mn.min_notional_usd = notion
                mn.updated_at = now
            await session.commit()
        return {
            "symbol": base,
            "account_type": at,
            "broker_id": bid,
            "contract_size": float(contract_size),
            "volume_min": float(volume_min),
            "volume_max": float(volume_max),
            "volume_step": float(volume_step),
            "tick_size": float(tick_size),
            "source": source,
        }

    async def resolve_instrument_spec(
        self,
        symbol: str,
        *,
        account_type: str = "standard",
        broker_id: str | None = None,
        allow_template_fallback: bool = True,
    ) -> tuple[Any, str]:
        """
        Resolve InstrumentSpec from broker table, then optional template.
        Returns (spec|None, source_label).
        """
        base = symbol.upper().split(".")[0]
        at = (account_type or "standard").strip().lower()
        bid = (broker_id or "default").strip() or "default"
        async with async_session_factory() as session:
            q = await session.execute(
                select(BrokerInstrumentSpec).where(
                    BrokerInstrumentSpec.symbol == base,
                    BrokerInstrumentSpec.account_type == at,
                    BrokerInstrumentSpec.broker_id == bid,
                )
            )
            row = q.scalar_one_or_none()
            if row is None and bid != "default":
                q2 = await session.execute(
                    select(BrokerInstrumentSpec).where(
                        BrokerInstrumentSpec.symbol == base,
                        BrokerInstrumentSpec.account_type == at,
                        BrokerInstrumentSpec.broker_id == "default",
                    )
                )
                row = q2.scalar_one_or_none()
            if row is not None:
                spec = instrument_spec_from_broker(
                    base,
                    contract_size=float(row.contract_size),
                    volume_min=float(row.volume_min),
                    volume_max=float(row.volume_max),
                    volume_step=float(row.volume_step),
                    tick_size=float(row.tick_size),
                    tick_value=float(row.tick_value) if row.tick_value is not None else None,
                    base_currency=row.base_currency,
                    quote_currency=row.quote_currency,
                    profit_currency=row.profit_currency,
                )
                return spec, f"broker_spec:{row.source}"
        if allow_template_fallback:
            tmpl = default_spec_for_symbol(base)
            if tmpl is not None:
                return tmpl, "template_fallback"
        return None, "missing"

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
        require_margin_check: bool = True,
    ) -> dict[str, Any]:
        """
        1) AEGIS assesses per-trade risk % from client tolerance + portfolio state.
        2) Size by stop-loss: volume = (equity * assessed_risk%) / loss_per_lot.

        Client configures risk *tolerance* only — not a fixed per-trade %.
        """
        state = await self.get_state(account_id)
        if state is None:
            return {"allow": False, "volume": 0.0, "reason": "account_not_found"}

        # Authoritative account currency from profile (do not silently assume USD)
        stored_ccy = str(state.get("account_currency") or "USD").upper()
        if account_currency is None or (account_currency == "USD" and stored_ccy and stored_ccy != "USD"):
            # Caller omitted or left default while profile is non-USD
            if account_currency == "USD" and stored_ccy != "USD":
                account_currency = stored_ccy
            elif not account_currency:
                account_currency = stored_ccy
        account_currency = (account_currency or stored_ccy or "USD").upper()

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

        acct_type = str(state.get("account_type") or "standard")
        acct_ccy = (account_currency or state.get("account_currency") or "USD").upper()
        broker = state.get("broker_id")

        spec_source = "caller"
        if instrument_spec is not None:
            spec = instrument_spec
        else:
            spec, spec_source = await self.resolve_instrument_spec(
                sym, account_type=acct_type, broker_id=broker, allow_template_fallback=True
            )
        if spec is None:
            return {
                "allow": False,
                "volume": 0.0,
                "reason": "instrument_spec_unavailable",
                "symbol": sym,
                "account_type": acct_type,
                "client_risk_tolerance_pct": pct,
                "aegis_per_trade_risk_pct": per_trade_pct,
                "sizing_audit": {
                    "account_id": account_id,
                    "account_type": acct_type,
                    "rejection": "instrument_spec_unavailable",
                },
            }

        rates = dict(fx_rates or {})
        rates.update(fx_rates_for_pair_price(sym, ep))

        plan_max = float(get_max_lot(plan_code))
        m_lot = margin_per_lot
        if m_lot is None and hasattr(spec, "tick_value_account"):
            # margin may be supplied by broker table via resolve
            pass
        # Pull margin_per_lot from broker row when available
        if m_lot is None:
            try:
                async with async_session_factory() as session:
                    q = await session.execute(
                        select(BrokerInstrumentSpec).where(
                            BrokerInstrumentSpec.symbol == sym,
                            BrokerInstrumentSpec.account_type == acct_type,
                        ).limit(1)
                    )
                    brow = q.scalar_one_or_none()
                    if brow is not None and brow.margin_per_lot is not None:
                        m_lot = float(brow.margin_per_lot)
            except Exception:
                pass

        # Resolve free margin: explicit arg wins; else last MT5-reported value (never equity)
        avail = available_margin
        margin_age_sec: float | None = None
        margin_src = "caller" if avail is not None else "state"
        if avail is None:
            stored = state.get("available_margin_usd")
            if stored is not None:
                avail = float(stored)
        margin_ts_raw = state.get("margin_updated_at")
        if margin_ts_raw:
            try:
                if isinstance(margin_ts_raw, str):
                    ts = datetime.fromisoformat(margin_ts_raw.replace("Z", "+00:00"))
                else:
                    ts = margin_ts_raw
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                margin_age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
            except Exception:
                margin_age_sec = None

        if require_margin_check:
            if avail is None or m_lot is None:
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "margin_data_missing",
                    "client_risk_tolerance_pct": pct,
                    "aegis_per_trade_risk_pct": per_trade_pct,
                    "sizing_method": "aegis_assessed_stop_risk",
                    "sizing_audit": {
                        "account_id": account_id,
                        "available_margin": avail,
                        "margin_per_lot": m_lot,
                        "margin_source": margin_src,
                        "margin_age_sec": margin_age_sec,
                        "rejection": "margin_data_missing",
                    },
                }
            # Stale only when using persisted state (caller-supplied values are treated as live)
            if margin_src == "state" and (
                margin_age_sec is None or margin_age_sec > MARGIN_STALE_SECONDS
            ):
                return {
                    "allow": False,
                    "volume": 0.0,
                    "reason": "margin_data_stale",
                    "client_risk_tolerance_pct": pct,
                    "aegis_per_trade_risk_pct": per_trade_pct,
                    "sizing_method": "aegis_assessed_stop_risk",
                    "sizing_audit": {
                        "account_id": account_id,
                        "available_margin": avail,
                        "margin_per_lot": m_lot,
                        "margin_source": margin_src,
                        "margin_age_sec": margin_age_sec,
                        "stale_after_sec": MARGIN_STALE_SECONDS,
                        "rejection": "margin_data_stale",
                    },
                }

        result = size_by_stop_risk(
            equity=float(equity),
            risk_pct=per_trade_pct,
            entry_price=ep,
            stop_loss=slp,
            side=side_u,  # type: ignore[arg-type]
            spec=spec,
            account_currency=acct_ccy,
            fx_rates=rates,
            open_risk_usd=0.0,
            risk_budget_override=trade_budget,
            available_margin=float(avail) if avail is not None else None,
            margin_per_lot=m_lot,
            plan_max_volume=plan_max,
            require_margin_check=bool(require_margin_check),
        )
        out = result.to_dict()
        vol = float(out.get("volume") or 0.0)
        if out.get("allow") and vol <= 0:
            out["allow"] = False
            out["reason"] = "invalid_volume_after_sizing"
            out["volume"] = 0.0

        sizing_audit = {
            "account_id": account_id,
            "account_type": acct_type,
            "account_currency": acct_ccy,
            "broker_id": broker,
            "equity": float(equity),
            "instrument": sym,
            "contract_size": getattr(spec, "contract_size", None),
            "volume_min": getattr(spec, "volume_min", None),
            "volume_max": getattr(spec, "volume_max", None),
            "volume_step": getattr(spec, "volume_step", None),
            "tick_size": getattr(spec, "tick_size", None),
            "entry_price": ep,
            "stop_price": slp,
            "stop_distance": stop_dist,
            "atr14": atr14,
            "assessed_risk_pct": per_trade_pct,
            "risk_budget": trade_budget,
            "raw_lots": out.get("raw_lots"),
            "final_volume": out.get("volume"),
            "estimated_monetary_risk": out.get("estimated_monetary_risk"),
            "required_margin": out.get("required_margin"),
            "available_margin": avail if avail is not None else available_margin,
            "margin_per_lot": m_lot,
            "margin_source": margin_src,
            "margin_age_sec": margin_age_sec,
            "require_margin_check": bool(require_margin_check),
            "margin_check_status": out.get("margin_check_status"),
            "accepted": bool(out.get("allow")),
            "reason": out.get("reason"),
            "spec_source": spec_source,
        }
        out["sizing_audit"] = sizing_audit
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
        out["account_type"] = acct_type
        out["account_currency"] = acct_ccy
        return out

    async def record_open_risk(self, account_id: str, delta_usd: float) -> None:
        """Increment open risk under row lock (concurrent-safe)."""
        if delta_usd is None:
            return
        d = float(delta_usd)
        if d == 0.0:
            return
        async with async_session_factory() as session:
            q = await session.execute(
                select(Subscription)
                .where(Subscription.account_id == account_id)
                .with_for_update()
            )
            row = q.scalar_one_or_none()
            if row is None:
                return
            row.open_risk_usd = max(0.0, float(row.open_risk_usd or 0.0) + d)
            await session.commit()

    async def release_open_risk(self, account_id: str, delta_usd: float) -> None:
        """Release open risk on broker-confirmed close (floor at 0, row-locked)."""
        if delta_usd is None:
            return
        d = abs(float(delta_usd))
        if d == 0.0:
            return
        async with async_session_factory() as session:
            q = await session.execute(
                select(Subscription)
                .where(Subscription.account_id == account_id)
                .with_for_update()
            )
            row = q.scalar_one_or_none()
            if row is None:
                return
            row.open_risk_usd = max(0.0, float(row.open_risk_usd or 0.0) - d)
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
