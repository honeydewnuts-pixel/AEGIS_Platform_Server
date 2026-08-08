"""

Project : AEGIS
System : Autonomous Enterprise Global Intelligence System
Company : Honeydewnuts Nigerian Limited

File : mt5_adapter.py
Version : 2.1.1 - Schema Aligned

Purpose

MetaTrader 5 implementation of the BrokerAdapter v2.1 interface.
SCHEMA ALIGNED: Matches trading.py and trading_entities.py exactly.

NOTE

This adapter is the ONLY location in AEGIS that communicates directly
with the MetaTrader5 Python SDK.

"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List

import MetaTrader5 as mt5

from app.core.logging import configure_logging
from app.schemas.trading import (
    MarketOrderRequest,
    PendingOrderRequest,
    ModifyPositionRequest,
    ClosePositionRequest,
    TradeExecutionResponse,
)
from app.schemas.trading_entities import (
    Position,
    PendingOrder,
    AccountInfo,
    SymbolInfo,
)
from app.services.broker_adapter_interface import BrokerAdapter

logger = configure_logging(__name__)

class MT5Adapter(BrokerAdapter):
    """
    Concrete MetaTrader 5 implementation of BrokerAdapter v2.1.
    All MetaTrader5 SDK interaction is isolated inside this class.
    """

    ADAPTER_VERSION = "2.1.1"

    def __init__(self) -> None:
        self._connected: bool = False
        self._credentials: dict[str, Any] | None = None
        self._broker_name: str = "MetaTrader5"

    # ==========================================================
    # CONNECTION CONTRACT
    # ==========================================================

    async def connect(self, credentials: dict[str, Any]) -> bool:
        """Initialize the MT5 terminal and authenticate with the broker."""
        self._credentials = credentials
        try:
            if not mt5.initialize():
                logger.error("MT5 initialize failed: %s", mt5.last_error())
                self._connected = False
                return False

            login_ok = mt5.login(
                login=int(credentials["login"]),
                password=str(credentials["password"]),
                server=str(credentials["server"]),
            )

            if not login_ok:
                logger.error("MT5 login failed: %s", mt5.last_error())
                mt5.shutdown()
                self._connected = False
                return False

            self._connected = True
            logger.info("Connected to MT5 account %s", credentials["login"])
            return True

        except Exception:
            logger.exception("Unexpected MT5 connection error")
            try:
                mt5.shutdown()
            except Exception:
                pass
            self._connected = False
            return False

    async def disconnect(self) -> bool:
        """Shutdown the MT5 terminal connection."""
        try:
            mt5.shutdown()
            self._connected = False
            logger.info("MT5 connection closed")
            return True
        except Exception:
            logger.exception("Failed to shutdown MT5")
            self._connected = False
            return False

    async def is_connected(self) -> bool:
        """Returns True only if the adapter believes it is connected and MT5 terminal is available."""
        try:
            terminal = mt5.terminal_info()
            return self._connected and terminal is not None
        except Exception:
            logger.exception("Unable to determine MT5 connection state")
            return False

    async def reconnect(self) -> bool:
        """Reconnect using previously stored credentials."""
        if self._credentials is None:
            logger.warning("Reconnect requested without stored credentials")
            return False
        await self.disconnect()
        return await self.connect(self._credentials)

    # ==========================================================
    # OPERATIONAL CONTRACT
    # ==========================================================

    async def health_check(self) -> dict[str, Any]:
        """Returns the standard BrokerAdapter v2.1 health payload."""
        connected = await self.is_connected()
        return {
            "healthy": connected,
            "connected": connected,
            "broker": self._broker_name,
            "adapter_version": self.ADAPTER_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ==========================================================
    # EXECUTION CONTRACT
    # ==========================================================

    async def place_market_order(self, request: MarketOrderRequest) -> TradeExecutionResponse:
        """Place market buy/sell order via MT5.order_send"""
        try:
            if not await self.is_connected():
                return TradeExecutionResponse(success=False, ticket=0, message="Not connected", price=0.0, error_code=-1)

            symbol_info = mt5.symbol_info(request.symbol)
            if symbol_info is None:
                return TradeExecutionResponse(success=False, ticket=0, message="Symbol not found", price=0.0, error_code=-3)

            trade_type = mt5.ORDER_TYPE_BUY if request.order_type == "BUY" else mt5.ORDER_TYPE_SELL
            price = symbol_info.ask if request.order_type == "BUY" else symbol_info.bid

            trade_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": request.symbol,
                "volume": float(request.volume),
                "type": trade_type,
                "price": price,
                "sl": request.stop_loss,
                "tp": request.take_profit,
                "deviation": 20,
                "magic": 234000,
                "comment": "AEGIS v2.1",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(trade_request)
            if result is None or result.retcode!= mt5.TRADE_RETCODE_DONE:
                err = mt5.last_error()
                return TradeExecutionResponse(success=False, ticket=0, message=f"Order failed: {err}", price=0.0, error_code=result.retcode if result else -1)

            return TradeExecutionResponse(success=True, ticket=result.order, message="Market order executed", price=result.price, error_code=0)

        except Exception as e:
            logger.exception("place_market_order error")
            return TradeExecutionResponse(success=False, ticket=0, message=str(e), price=0.0, error_code=-99)

    async def place_pending_order(self, request: PendingOrderRequest) -> TradeExecutionResponse:
        """Place pending order via MT5.order_send"""
        try:
            if not await self.is_connected():
                return TradeExecutionResponse(success=False, ticket=0, message="Not connected", price=0.0, error_code=-1)

            order_type_map = {
                "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT,
                "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
                "buy_stop": mt5.ORDER_TYPE_BUY_STOP,
                "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            }

            trade_request = {
                "action": mt5.TRADE_ACTION_PENDING,
                "symbol": request.symbol,
                "volume": float(request.volume),
                "type": order_type_map[request.order_type],
                "price": float(request.price),
                "sl": request.stop_loss,
                "tp": request.take_profit,
                "deviation": 20,
                "magic": 234000,
                "comment": "AEGIS v2.1",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }

            result = mt5.order_send(trade_request)
            if result is None or result.retcode!= mt5.TRADE_RETCODE_DONE:
                err = mt5.last_error()
                return TradeExecutionResponse(success=False, ticket=0, message=f"Pending order failed: {err}", price=0.0, error_code=result.retcode if result else -1)

            return TradeExecutionResponse(success=True, ticket=result.order, message="Pending order placed", price=result.price, error_code=0)

        except Exception as e:
            logger.exception("place_pending_order error")
            return TradeExecutionResponse(success=False, ticket=0, message=str(e), price=0.0, error_code=-99)

    async def modify_position(self, request: ModifyPositionRequest) -> TradeExecutionResponse:
        """Modify SL/TP via MT5.order_send with TRADE_ACTION_SLTP"""
        try:
            if not await self.is_connected():
                return TradeExecutionResponse(success=False, ticket=0, message="Not connected", price=0.0, error_code=-1)

            trade_request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": request.ticket,
                "sl": request.stop_loss,
                "tp": request.take_profit,
            }

            result = mt5.order_send(trade_request)
            if result is None or result.retcode!= mt5.TRADE_RETCODE_DONE:
                err = mt5.last_error()
                return TradeExecutionResponse(success=False, ticket=0, message=f"Modify failed: {err}", price=0.0, error_code=result.retcode if result else -1)

            return TradeExecutionResponse(success=True, ticket=request.ticket, message="Position modified", price=0.0, error_code=0)

        except Exception as e:
            logger.exception("modify_position error")
            return TradeExecutionResponse(success=False, ticket=0, message=str(e), price=0.0, error_code=-99)

    async def close_position(self, request: ClosePositionRequest) -> TradeExecutionResponse:
        """Close position via MT5.order_send with TRADE_ACTION_DEAL"""
        try:
            if not await self.is_connected():
                return TradeExecutionResponse(success=False, ticket=0, message="Not connected", price=0.0, error_code=-1)

            position = mt5.positions_get(ticket=request.ticket)
            if not position:
                return TradeExecutionResponse(success=False, ticket=0, message="Position not found", price=0.0, error_code=-2)

            position = position[0]
            trade_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            symbol_info = mt5.symbol_info(position.symbol)
            price = symbol_info.bid if trade_type == mt5.ORDER_TYPE_SELL else symbol_info.ask

            trade_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": float(position.volume),
                "type": trade_type,
                "position": request.ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "AEGIS close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(trade_request)
            if result is None or result.retcode!= mt5.TRADE_RETCODE_DONE:
                err = mt5.last_error()
                return TradeExecutionResponse(success=False, ticket=0, message=f"Close failed: {err}", price=0.0, error_code=result.retcode if result else -1)

            return TradeExecutionResponse(success=True, ticket=request.ticket, message="Position closed", price=result.price, error_code=0)

        except Exception as e:
            logger.exception("close_position error")
            return TradeExecutionResponse(success=False, ticket=0, message=str(e), price=0.0, error_code=-99)

    async def cancel_pending_order(self, ticket: int) -> TradeExecutionResponse:
        """Cancel pending order via MT5.order_send with TRADE_ACTION_REMOVE"""
        try:
            if not await self.is_connected():
                return TradeExecutionResponse(success=False, ticket=0, message="Not connected", price=0.0, error_code=-1)

            trade_request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": ticket,
            }

            result = mt5.order_send(trade_request)
            if result is None or result.retcode!= mt5.TRADE_RETCODE_DONE:
                err = mt5.last_error()
                return TradeExecutionResponse(success=False, ticket=0, message=f"Cancel failed: {err}", price=0.0, error_code=result.retcode if result else -1)

            return TradeExecutionResponse(success=True, ticket=ticket, message="Pending order cancelled", price=0.0, error_code=0)

        except Exception as e:
            logger.exception("cancel_pending_order error")
            return TradeExecutionResponse(success=False, ticket=0, message=str(e), price=0.0, error_code=-99)

    # ==========================================================
    # DATA + INFO CONTRACT
    # ==========================================================

    async def get_positions(self) -> List[Position]:
        """Get all open positions mapped to Position model"""
        try:
            if not await self.is_connected():
                return []
            positions = mt5.positions_get()
            if positions is None:
                return []
            return [self._map_position_to_model(p) for p in positions]
        except Exception:
            logger.exception("get_positions error")
            return []

    async def get_orders(self) -> List[PendingOrder]:
        """Get all pending orders mapped to PendingOrder model"""
        try:
            if not await self.is_connected():
                return []
            orders = mt5.orders_get()
            if orders is None:
                return []
            return [self._map_order_to_model(o) for o in orders]
        except Exception:
            logger.exception("get_orders error")
            return []

    async def get_account_info(self) -> AccountInfo | None:
        """Get account info mapped to AccountInfo model"""
        try:
            if not await self.is_connected():
                return None
            acc = mt5.account_info()
            if acc is None:
                return None
            return AccountInfo(
                login=acc.login,
                server=acc.server,
                company=acc.company,
                name=acc.name,
                balance=acc.balance,
                equity=acc.equity,
                margin=acc.margin,
                margin_free=acc.margin_free,
                currency=acc.currency,
                leverage=acc.leverage,
            )
        except Exception:
            logger.exception("get_account_info error")
            return None

    async def get_symbol_info(self, symbol: str) -> SymbolInfo | None:
        """Get symbol info mapped to SymbolInfo model"""
        try:
            if not await self.is_connected():
                return None
            sym = mt5.symbol_info(symbol)
            if sym is None:
                return None
            return SymbolInfo(
                name=sym.name,
                bid=sym.bid,
                ask=sym.ask,
                point=sym.point,
                digits=sym.digits,
                trade_mode=sym.trade_mode,
            )
        except Exception:
            logger.exception("get_symbol_info error")
            return None

    # ==========================================================
    # INTERNAL HELPERS - SCHEMA ALIGNED v2.1.1
    # ==========================================================

    def _map_position_to_model(self, mt5_pos) -> Position:
        """Convert MT5 position to Position. Matches trading_entities.py exactly"""
        return Position(
            ticket=mt5_pos.ticket,
            symbol=mt5_pos.symbol,
            type="BUY" if mt5_pos.type == mt5.ORDER_TYPE_BUY else "SELL",
            volume=mt5_pos.volume,
            open_price=mt5_pos.price_open,
            current_price=mt5_pos.price_current,
            sl=mt5_pos.sl,
            tp=mt5_pos.tp,
            profit=mt5_pos.profit,
            swap=mt5_pos.swap,
            open_time=datetime.fromtimestamp(mt5_pos.time, tz=timezone.utc)
        )

    def _map_order_to_model(self, mt5_order) -> PendingOrder:
        """Convert MT5 order to PendingOrder. Matches trading_entities.py exactly"""
        type_map = {
            mt5.ORDER_TYPE_BUY_LIMIT: "buy_limit",
            mt5.ORDER_TYPE_SELL_LIMIT: "sell_limit",
            mt5.ORDER_TYPE_BUY_STOP: "buy_stop",
            mt5.ORDER_TYPE_SELL_STOP: "sell_stop",
        }
        return PendingOrder(
            ticket=mt5_order.ticket,
            symbol=mt5_order.symbol,
            type=type_map.get(mt5_order.type, "unknown"),
            volume=mt5_order.volume_current,
            price=mt5_order.price_open,
            sl=mt5_order.sl,
            tp=mt5_order.tp,
            open_time=datetime.fromtimestamp(mt5_order.time_setup, tz=timezone.utc)
        )
