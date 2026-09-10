"""AEGIS V42 execution, risk and safety gate.

This module is deliberately broker-independent and fail-closed. It does not
place orders. It validates whether a proposed paper/execution action is
eligible to reach an adapter. Production authorization is an explicit,
independent gate and is FALSE by default.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class Decision(str, Enum):
    ALLOW_PAPER = "ALLOW_PAPER"
    ALLOW_LIVE = "ALLOW_LIVE"
    REJECT = "REJECT"
    KILL_SWITCH = "KILL_SWITCH"


class ExecutionState(str, Enum):
    IDLE = "IDLE"
    SIGNAL_ACCEPTED = "SIGNAL_ACCEPTED"
    ORDER_QUEUED = "ORDER_QUEUED"
    FILLED = "FILLED"
    MANAGING = "MANAGING"
    EXIT_REQUESTED = "EXIT_REQUESTED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"
    HALTED = "HALTED"


@dataclass(frozen=True)
class SafetyConfig:
    max_spread_atr: float = 0.25
    max_signal_age_seconds: int = 360
    max_positions_per_symbol: int = 1
    max_total_positions: int = 1
    max_duration_bars: int = 72
    initial_stop_atr: float = 1.5
    trailing_atr: float = 0.75
    break_even_r: float = 1.0
    production_authorized: bool = False
    live_enabled: bool = False


@dataclass(frozen=True)
class MarketState:
    symbol: str
    timeframe: str
    bid: float
    ask: float
    atr: float
    bar_timestamp: datetime
    observed_at: datetime


@dataclass(frozen=True)
class OrderIntent:
    client_order_id: str
    symbol: str
    timeframe: str
    side: str
    entry_price: float
    stop_price: float
    atr: float
    signal_timestamp: datetime
    mode: str = "PAPER"


@dataclass(frozen=True)
class PositionState:
    symbol: str
    side: str
    entry_price: float
    stop_price: float
    bars_open: int = 0
    be_armed: bool = False


@dataclass(frozen=True)
class GateResult:
    decision: Decision
    reasons: tuple[str, ...] = ()


@dataclass
class KillSwitch:
    halted: bool = False
    reason: str | None = None
    activated_at: datetime | None = None

    def activate(self, reason: str) -> None:
        self.halted = True
        self.reason = reason
        self.activated_at = datetime.now(timezone.utc)

    def reset(self) -> None:
        self.halted = False
        self.reason = None
        self.activated_at = None


class ExecutionStateMachine:
    """Strict lifecycle with no implicit state skipping."""

    _allowed = {
        ExecutionState.IDLE: {ExecutionState.SIGNAL_ACCEPTED, ExecutionState.HALTED},
        ExecutionState.SIGNAL_ACCEPTED: {ExecutionState.ORDER_QUEUED, ExecutionState.REJECTED, ExecutionState.HALTED},
        ExecutionState.ORDER_QUEUED: {ExecutionState.FILLED, ExecutionState.REJECTED, ExecutionState.HALTED},
        ExecutionState.FILLED: {ExecutionState.MANAGING, ExecutionState.EXIT_REQUESTED, ExecutionState.HALTED},
        ExecutionState.MANAGING: {ExecutionState.EXIT_REQUESTED, ExecutionState.HALTED},
        ExecutionState.EXIT_REQUESTED: {ExecutionState.CLOSED, ExecutionState.HALTED},
        ExecutionState.CLOSED: {ExecutionState.IDLE, ExecutionState.HALTED},
        ExecutionState.REJECTED: {ExecutionState.IDLE, ExecutionState.HALTED},
        ExecutionState.HALTED: {ExecutionState.IDLE},
    }

    def __init__(self) -> None:
        self.state = ExecutionState.IDLE

    def transition(self, target: ExecutionState) -> ExecutionState:
        if target not in self._allowed[self.state]:
            raise ValueError(f"Invalid execution transition: {self.state} -> {target}")
        self.state = target
        return self.state


class V42SafetyGate:
    """Central pre-execution gate for rulebook/risk/data/safety controls."""

    def __init__(self, config: SafetyConfig | None = None, kill_switch: KillSwitch | None = None) -> None:
        self.config = config or SafetyConfig()
        self.kill_switch = kill_switch or KillSwitch()

    def validate_market(self, market: MarketState, *, now: datetime | None = None) -> GateResult:
        reasons: list[str] = []
        if not market.symbol or not market.timeframe:
            reasons.append("UNKNOWN_INSTRUMENT_OR_TIMEFRAME")
        if market.bid <= 0 or market.ask <= 0 or market.ask < market.bid:
            reasons.append("INVALID_BID_ASK")
        if market.atr <= 0:
            reasons.append("INVALID_ATR")
        spread = market.ask - market.bid
        if market.atr > 0 and spread / market.atr > self.config.max_spread_atr:
            reasons.append("SPREAD_ATR_LIMIT")
        current = now or datetime.now(timezone.utc)
        age = (current - market.bar_timestamp).total_seconds()
        if age < 0 or age > self.config.max_signal_age_seconds:
            reasons.append("STALE_OR_FUTURE_BAR")
        if self.kill_switch.halted:
            return GateResult(Decision.KILL_SWITCH, (self.kill_switch.reason or "KILL_SWITCH_ACTIVE",))
        return GateResult(Decision.REJECT if reasons else Decision.ALLOW_PAPER, tuple(reasons))

    def validate_order(
        self,
        intent: OrderIntent,
        market: MarketState,
        positions: Iterable[PositionState],
        *,
        qualified_rulebook: bool,
        now: datetime | None = None,
    ) -> GateResult:
        if self.kill_switch.halted:
            return GateResult(Decision.KILL_SWITCH, (self.kill_switch.reason or "KILL_SWITCH_ACTIVE",))
        reasons: list[str] = []
        market_result = self.validate_market(market, now=now)
        reasons.extend(market_result.reasons)
        if not qualified_rulebook:
            reasons.append("NO_QUALIFIED_RULEBOOK")
        if intent.symbol != market.symbol or intent.timeframe != market.timeframe:
            reasons.append("MARKET_INTENT_MISMATCH")
        if intent.side not in {"BUY", "SELL"}:
            reasons.append("INVALID_SIDE")
        if intent.atr <= 0 or market.atr <= 0:
            reasons.append("INVALID_ATR")
        if intent.mode.upper() == "LIVE":
            if not self.config.live_enabled:
                reasons.append("LIVE_EXECUTION_DISABLED")
            if not self.config.production_authorized:
                reasons.append("PRODUCTION_AUTHORIZATION_REQUIRED")
        elif intent.mode.upper() != "PAPER":
            reasons.append("UNKNOWN_EXECUTION_MODE")

        active = list(positions)
        symbol_count = sum(p.symbol == intent.symbol for p in active)
        if symbol_count >= self.config.max_positions_per_symbol:
            reasons.append("ONE_POSITION_PER_SYMBOL")
        if len(active) >= self.config.max_total_positions:
            reasons.append("TOTAL_POSITION_LIMIT")

        expected_stop_distance = self.config.initial_stop_atr * market.atr
        if intent.side == "BUY" and intent.stop_price >= intent.entry_price:
            reasons.append("INVALID_LONG_STOP")
        if intent.side == "SELL" and intent.stop_price <= intent.entry_price:
            reasons.append("INVALID_SHORT_STOP")
        if abs(intent.entry_price - intent.stop_price) + 1e-12 < expected_stop_distance:
            reasons.append("STOP_DISTANCE_BELOW_FLOOR")

        decision = Decision.REJECT if reasons else (Decision.ALLOW_LIVE if intent.mode.upper() == "LIVE" else Decision.ALLOW_PAPER)
        return GateResult(decision, tuple(dict.fromkeys(reasons)))

    def risk_stop(self, position: PositionState, market: MarketState) -> float:
        """Return a monotonic trailing stop for the current bar."""
        if position.side == "BUY":
            candidate = market.bid - self.config.trailing_atr * market.atr
            if position.be_armed:
                candidate = max(candidate, position.entry_price)
            return max(position.stop_price, candidate)
        candidate = market.ask + self.config.trailing_atr * market.atr
        if position.be_armed:
            candidate = min(candidate, position.entry_price)
        return min(position.stop_price, candidate)

    def should_break_even(self, position: PositionState, market: MarketState) -> bool:
        one_r = self.config.initial_stop_atr * market.atr
        if position.side == "BUY":
            return market.bid >= position.entry_price + self.config.break_even_r * one_r
        return market.ask <= position.entry_price - self.config.break_even_r * one_r

    def duration_ok(self, position: PositionState) -> bool:
        return position.bars_open <= self.config.max_duration_bars
