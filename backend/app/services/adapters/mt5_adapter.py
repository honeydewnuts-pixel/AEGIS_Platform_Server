"""MetaTrader 5 broker adapter for the AEGIS Windows worker.

V3 DEMO EXECUTION ADAPTER
- Runs only on the Windows machine that has the real MT5 terminal.
- Uses the MetaTrader5 terminal API; no broker REST/HTTP trading API.
- Refuses REAL accounts at connection time.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from app.schemas.trading import (
    MarketOrderRequest, PendingOrderRequest, ModifyPositionRequest,
    ClosePositionRequest, TradeExecutionResponse,
)
from app.schemas.trading_entities import AccountInfo, Position, PendingOrder, SymbolInfo, OrderType
from app.services.broker_adapter_interface import BrokerAdapter


class MT5Adapter(BrokerAdapter):
    ADAPTER_VERSION = "V3-MT5-1.0.0"
    MAGIC = 236600
    DEVIATION = 20

    def __init__(self) -> None:
        self.mt5 = None
        self.credentials: dict[str, Any] = {}
        self._connected = False

    def _load(self):
        if self.mt5 is None:
            try:
                import MetaTrader5 as mt5
            except ImportError as exc:
                raise RuntimeError(
                    "MetaTrader5==5.0.4993 is required on the Windows MT5 worker."
                ) from exc
            self.mt5 = mt5
        return self.mt5

    def _connect_sync(self, credentials: dict[str, Any]) -> bool:
        mt5 = self._load()
        login = int(credentials.get("login") or 0)
        password = str(credentials.get("password") or credentials.get("trading_password") or "")
        server = str(credentials.get("server") or "").strip()
        if not login or not password or not server:
            raise ValueError("MT5 login, trading password and server are required.")

        if not mt5.initialize(login=login, password=password, server=server):
            code = mt5.last_error()
            raise RuntimeError(f"MT5 initialize/login failed: {code}")

        info = mt5.account_info()
        if info is None:
            mt5.shutdown()
            raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")

        # Hard safety gate: this build may execute DEMO accounts only.
        demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        trade_mode = int(getattr(info, "trade_mode", -1))
        if trade_mode != int(demo_mode):
            mt5.shutdown()
            raise RuntimeError(
                f"AEGIS V3 DEMO-ONLY worker refused account trade_mode={trade_mode}."
            )

        self.credentials = dict(credentials)
        self._connected = True
        return True

    async def connect(self, credentials: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._connect_sync, credentials)

    async def disconnect(self) -> bool:
        def _d():
            if self.mt5 is not None:
                self.mt5.shutdown()
            self._connected = False
            return True
        return await asyncio.to_thread(_d)

    async def is_connected(self) -> bool:
        if not self._connected:
            return False
        return await asyncio.to_thread(lambda: self.mt5.account_info() is not None)

    async def reconnect(self) -> bool:
        return await self.connect(self.credentials)

    def _ensure_symbol(self, symbol: str):
        mt5 = self._load()
        symbol = symbol.strip()
        if not symbol:
            raise ValueError("Symbol is required.")
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"MT5 symbol not found: {symbol}")
        if not info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"MT5 symbol is unavailable: {symbol}")
        return info

    def _fillings(self, info):
        mt5 = self._load()
        mode = int(getattr(info, "filling_mode", 0))
        candidates = []
        for name in ("ORDER_FILLING_IOC", "ORDER_FILLING_FOK", "ORDER_FILLING_RETURN"):
            value = getattr(mt5, name, None)
            if value is not None:
                # symbol_info.filling_mode is broker/platform-specific; IOC is
                # the safest first attempt for most market-execution symbols.
                if value not in candidates:
                    candidates.append(value)
        return candidates or [getattr(mt5, "ORDER_FILLING_RETURN", 2)]

    def _send_market_sync(self, request: MarketOrderRequest):
        mt5 = self._load()
        info = self._ensure_symbol(request.symbol)
        tick = mt5.symbol_info_tick(request.symbol)
        if tick is None:
            raise RuntimeError(f"No live tick available for {request.symbol}")

        side = request.order_type.upper()
        order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
        price = float(tick.ask if side == "BUY" else tick.bid)
        volume = float(request.volume)
        step = float(getattr(info, "volume_step", 0.01) or 0.01)
        vmin = float(getattr(info, "volume_min", step) or step)
        vmax = float(getattr(info, "volume_max", volume) or volume)
        volume = max(vmin, min(vmax, round(round(volume / step) * step, 8)))

        base = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": request.symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": self.DEVIATION,
            "magic": self.MAGIC,
            "comment": request.comment or "AEGIS V3 DEMO",
            "type_time": mt5.ORDER_TIME_GTC,
        }

        last = None
        for filling in self._fillings(info):
            result = mt5.order_send({**base, "type_filling": filling})
            last = result
            if result is None:
                continue
            if int(getattr(result, "retcode", -1)) != int(getattr(mt5, "TRADE_RETCODE_INVALID_FILL", 10030)):
                break

        if last is None:
            raise RuntimeError(f"MT5 order_send returned None: {mt5.last_error()}")

        ret = int(getattr(last, "retcode", -1))
        done = {
            int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)),
            int(getattr(mt5, "TRADE_RETCODE_PLACED", 10008)),
            int(getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)),
        }
        if ret not in done:
            return TradeExecutionResponse(
                success=False,
                ticket=int(getattr(last, "order", 0) or getattr(last, "deal", 0) or 0) or None,
                message=f"MT5 rejected {side} {request.symbol}: retcode={ret}, comment={getattr(last,'comment','')}",
                price=float(getattr(last, "price", 0) or price) or None,
                error_code=ret,
            )
        return TradeExecutionResponse(
            success=True,
            ticket=int(getattr(last, "order", 0) or getattr(last, "deal", 0) or 0) or None,
            message=f"AEGIS V3 DEMO {side} executed on {request.symbol}.",
            price=float(getattr(last, "price", 0) or price),
            error_code=ret,
        )

    async def place_market_order(self, request: MarketOrderRequest) -> TradeExecutionResponse:
        return await asyncio.to_thread(self._send_market_sync, request)

    async def place_pending_order(self, request: PendingOrderRequest) -> TradeExecutionResponse:
        def _send():
            mt5 = self._load()
            info = self._ensure_symbol(request.symbol)
            typemap = {
                "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
                "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
                "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
                "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP,
            }
            typ = typemap[request.order_type]
            req = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": request.symbol,
                "volume": float(request.volume),
                "type": typ,
                "price": float(request.price),
                "sl": float(request.sl or 0),
                "tp": float(request.tp or 0),
                "deviation": self.DEVIATION,
                "magic": self.MAGIC,
                "comment": "AEGIS V3 DEMO",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": getattr(mt5, "ORDER_FILLING_RETURN", 2),
            }
            result = mt5.order_send(req)
            if result is None:
                raise RuntimeError(f"MT5 order_send returned None: {mt5.last_error()}")
            ret = int(getattr(result, "retcode", -1))
            if ret != int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)):
                return TradeExecutionResponse(False, None, f"Pending order rejected: retcode={ret}, comment={getattr(result,'comment','')}", None, ret)
            return TradeExecutionResponse(True, int(getattr(result, "order", 0) or 0) or None, "Pending order placed.", float(getattr(result, "price", request.price) or request.price), ret)
        return await asyncio.to_thread(_send)

    async def modify_position(self, request: ModifyPositionRequest) -> TradeExecutionResponse:
        def _send():
            mt5 = self._load()
            pos = mt5.positions_get(ticket=int(request.ticket))
            if not pos:
                return TradeExecutionResponse(False, None, f"Position {request.ticket} not found.", None, None)
            p = pos[0]
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": p.symbol,
                "position": int(request.ticket),
                "sl": float(request.sl or 0),
                "tp": float(request.tp or 0),
                "magic": self.MAGIC,
            })
            if result is None:
                raise RuntimeError(f"MT5 order_send returned None: {mt5.last_error()}")
            ret = int(getattr(result, "retcode", -1))
            ok = ret == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
            return TradeExecutionResponse(ok, int(request.ticket), f"Position modification retcode={ret}.", None, ret)
        return await asyncio.to_thread(_send)

    async def close_position(self, request: ClosePositionRequest) -> TradeExecutionResponse:
        def _send():
            mt5 = self._load()
            pos = mt5.positions_get(ticket=int(request.ticket))
            if not pos:
                return TradeExecutionResponse(False, None, f"Position {request.ticket} not found.", None, None)
            p = pos[0]
            tick = mt5.symbol_info_tick(p.symbol)
            if tick is None:
                raise RuntimeError(f"No live tick for {p.symbol}")
            is_buy = int(getattr(p, "type", 0)) == int(getattr(mt5, "POSITION_TYPE_BUY", 0))
            typ = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
            price = float(tick.bid if is_buy else tick.ask)
            volume = float(request.volume or p.volume)
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": p.symbol,
                "volume": volume,
                "type": typ,
                "position": int(request.ticket),
                "price": price,
                "deviation": self.DEVIATION,
                "magic": self.MAGIC,
                "comment": "AEGIS V3 DEMO CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": getattr(mt5, "ORDER_FILLING_IOC", 1),
            })
            if result is None:
                raise RuntimeError(f"MT5 order_send returned None: {mt5.last_error()}")
            ret = int(getattr(result, "retcode", -1))
            ok = ret in {
                int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)),
                int(getattr(mt5, "TRADE_RETCODE_DONE_PARTIAL", 10010)),
            }
            return TradeExecutionResponse(ok, int(getattr(result, "order", 0) or getattr(result, "deal", 0) or 0) or None, f"Close retcode={ret}.", float(getattr(result, "price", 0) or price), ret)
        return await asyncio.to_thread(_send)

    async def cancel_pending_order(self, order_ticket: int) -> TradeExecutionResponse:
        def _send():
            mt5 = self._load()
            result = mt5.order_send({
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": int(order_ticket),
                "magic": self.MAGIC,
            })
            if result is None:
                raise RuntimeError(f"MT5 order_send returned None: {mt5.last_error()}")
            ret = int(getattr(result, "retcode", -1))
            ok = ret == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
            return TradeExecutionResponse(ok, int(order_ticket), f"Cancel retcode={ret}.", None, ret)
        return await asyncio.to_thread(_send)

    async def get_positions(self) -> list[Position]:
        def _get():
            mt5 = self._load()
            rows = mt5.positions_get() or []
            out = []
            for p in rows:
                typ = OrderType.BUY if int(getattr(p, "type", 0)) == int(getattr(mt5, "POSITION_TYPE_BUY", 0)) else OrderType.SELL
                out.append(Position(
                    ticket=int(p.ticket), symbol=str(p.symbol), type=typ,
                    volume=float(p.volume), open_price=float(p.price_open),
                    current_price=float(p.price_current), sl=float(p.sl) if p.sl else None,
                    tp=float(p.tp) if p.tp else None, profit=float(p.profit),
                    swap=float(p.swap), open_time=datetime.fromtimestamp(float(p.time), tz=timezone.utc),
                ))
            return out
        return await asyncio.to_thread(_get)

    async def get_orders(self) -> list[PendingOrder]:
        def _get():
            mt5 = self._load()
            rows = mt5.orders_get() or []
            out = []
            typemap = {
                getattr(mt5, "ORDER_TYPE_BUY_LIMIT", 2): OrderType.BUY_LIMIT,
                getattr(mt5, "ORDER_TYPE_SELL_LIMIT", 3): OrderType.SELL_LIMIT,
                getattr(mt5, "ORDER_TYPE_BUY_STOP", 4): OrderType.BUY_STOP,
                getattr(mt5, "ORDER_TYPE_SELL_STOP", 5): OrderType.SELL_STOP,
            }
            for o in rows:
                if int(getattr(o, "type", -1)) not in typemap:
                    continue
                out.append(PendingOrder(
                    ticket=int(o.ticket), symbol=str(o.symbol), type=typemap[int(o.type)],
                    volume=float(o.volume_current), price=float(o.price_open),
                    sl=float(o.sl) if o.sl else None, tp=float(o.tp) if o.tp else None,
                    open_time=datetime.fromtimestamp(float(o.time_setup), tz=timezone.utc),
                ))
            return out
        return await asyncio.to_thread(_get)

    async def get_account_info(self) -> AccountInfo:
        def _get():
            mt5 = self._load()
            a = mt5.account_info()
            if a is None:
                raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")
            return AccountInfo(
                login=int(a.login), server=str(a.server), company=str(a.company),
                name=str(a.name), balance=float(a.balance), equity=float(a.equity),
                margin=float(a.margin), margin_free=float(a.margin_free),
                currency=str(a.currency), leverage=int(a.leverage),
            )
        return await asyncio.to_thread(_get)

    async def get_symbol_info(self, symbol: str) -> SymbolInfo:
        def _get():
            mt5 = self._load()
            i = self._ensure_symbol(symbol)
            t = mt5.symbol_info_tick(symbol)
            if t is None:
                raise RuntimeError(f"No tick for {symbol}")
            return SymbolInfo(
                name=str(i.name), bid=float(t.bid), ask=float(t.ask),
                point=float(i.point), digits=int(i.digits), trade_mode=int(i.trade_mode),
            )
        return await asyncio.to_thread(_get)

    async def health_check(self) -> dict[str, Any]:
        def _h():
            mt5 = self._load()
            a = mt5.account_info()
            return {
                "healthy": a is not None,
                "connected": a is not None and self._connected,
                "broker": str(getattr(a, "server", "")) if a else "",
                "adapter_version": self.ADAPTER_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trade_mode": int(getattr(a, "trade_mode", -1)) if a else None,
                "demo_only": True,
            }
        return await asyncio.to_thread(_h)
