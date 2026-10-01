"""Hybrid Ratchet 70/30 + Lean CAP v2 withdrawal accounting (pure logic).

Does NOT place trades, size positions, or alter V53.6 entry/exit.
Operates only on realized net profit events and equity snapshots.

Rules:
- Before equity reaches ARM_MULTIPLE * start_equity: 100% compound, no withdrawals.
- On arm: CAP = ARM_MULTIPLE * start_equity.
- CAP never decreases on trading losses.
- When armed, not paused, equity > CAP after realized profit:
    excess = equity - CAP
    eligible += withdraw_pct * excess   (default 70%)
    CAP += retain_pct * excess          (default 30%)
- Lean CAP v2: CAP is hard-capped at LEAN_CAP_CEILING (by risk label).
    Any tentative CAP above the ceiling is swept into eligible (DEAD FREED)
    and CAP is reset to the ceiling. CAP never exceeds the ceiling again.
- Pause when equity < CAP * (1 - pause_dd); resume when equity >= CAP.
- Withdrawals are ledger entitlements, not trading losses.
- trade_id idempotency prevents double allocation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# Reference cash-test baseline: $1,000 start equity → absolute ceilings from 5Y stretch.
# Other start equities scale linearly: ceiling = start_equity * (ref_ceiling / ref_start).
LEAN_CAP_REF_START_EQUITY: float = 1_000.0
LEAN_CAP_REF_CEILING_BY_RISK: dict[float, float] = {
    0.5: 83_286.0,   # $1k @ 0.5% research baseline
    1.0: 783_300.0,  # $1k @ 1.0% research baseline
}


def resolve_lean_cap_multiple(risk_per_trade_pct: float) -> float:
    """CAP multiple of start equity at lean lock (from $1k cash-test reference)."""
    r = float(risk_per_trade_pct)
    refs = LEAN_CAP_REF_CEILING_BY_RISK
    if r not in refs:
        nearest = min(refs.keys(), key=lambda k: abs(k - r))
        r = nearest
    return refs[r] / LEAN_CAP_REF_START_EQUITY


def resolve_lean_cap_ceiling(risk_per_trade_pct: float, start_equity: float = 1_000.0) -> float:
    """Lean CAP ceiling for this account = start_equity × research multiple.

    Example: $500 start @ 0.5% → 500 × 83.286 = $41,643
             $2,000 start @ 1.0% → 2000 × 783.3 = $1,566,600
    """
    se = max(float(start_equity), 1e-9)
    return round(se * resolve_lean_cap_multiple(risk_per_trade_pct), 2)


@dataclass
class RatchetConfig:
    withdraw_pct: float = 0.70
    retain_pct: float = 0.30
    arm_multiple: float = 2.0
    pause_dd_from_cap: float = 0.20
    # None = derive from account risk_per_trade_pct via resolve_lean_cap_ceiling
    lean_cap_ceiling: float | None = None
    lean_cap_enabled: bool = True

    def validate(self) -> None:
        if abs(self.withdraw_pct + self.retain_pct - 1.0) > 1e-9:
            raise ValueError("withdraw_pct + retain_pct must equal 1.0")
        if self.arm_multiple < 1.0:
            raise ValueError("arm_multiple must be >= 1")
        if not (0.0 < self.pause_dd_from_cap < 1.0):
            raise ValueError("pause_dd_from_cap must be in (0, 1)")
        if self.lean_cap_ceiling is not None and self.lean_cap_ceiling <= 0:
            raise ValueError("lean_cap_ceiling must be positive when set")


@dataclass
class RatchetState:
    account_id: str
    start_equity: float
    mode: str = "portfolio"  # portfolio | per_pair
    risk_per_trade_pct: float = 0.5
    symbol: str | None = None  # set when mode=per_pair

    equity: float = 0.0
    cap: float = 0.0
    armed: bool = False
    paused: bool = False
    lean_locked: bool = False  # True once CAP has been clamped to lean ceiling

    cumulative_withdrawn: float = 0.0
    eligible_balance: float = 0.0
    retained_profit_total: float = 0.0
    realized_trading_pnl: float = 0.0
    dead_freed_total: float = 0.0  # CAP excess swept at lean ceiling

    processed_trade_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.equity <= 0:
            self.equity = float(self.start_equity)

    def snapshot(self) -> dict[str, Any]:
        d = asdict(self)
        d["processed_trade_ids"] = sorted(self.processed_trade_ids)
        d["total_value"] = round(self.equity + self.cumulative_withdrawn, 8)
        d["drawdown_from_cap_pct"] = None
        if self.armed and self.cap > 0:
            d["drawdown_from_cap_pct"] = round(max(0.0, (self.cap - self.equity) / self.cap * 100.0), 4)
        d["drawdown_from_start_pct"] = round(
            max(0.0, (self.start_equity - self.equity) / self.start_equity * 100.0), 4
        ) if self.start_equity > 0 else 0.0
        d["lean_cap_ceiling"] = resolve_lean_cap_ceiling(self.risk_per_trade_pct, self.start_equity)
        return d


@dataclass
class AllocationResult:
    applied: bool
    reason: str
    excess: float = 0.0
    to_eligible: float = 0.0
    to_cap: float = 0.0
    dead_freed: float = 0.0
    state: dict[str, Any] = field(default_factory=dict)


class HybridRatchetEngine:
    def __init__(self, config: RatchetConfig | None = None) -> None:
        self.config = config or RatchetConfig()
        self.config.validate()

    def lean_ceiling_for(self, state: RatchetState) -> float:
        if self.config.lean_cap_ceiling is not None:
            return float(self.config.lean_cap_ceiling)
        return resolve_lean_cap_ceiling(state.risk_per_trade_pct, state.start_equity)

    def seed(
        self,
        account_id: str,
        start_equity: float,
        *,
        mode: str = "portfolio",
        risk_per_trade_pct: float = 0.5,
        symbol: str | None = None,
    ) -> RatchetState:
        if start_equity <= 0:
            raise ValueError("start_equity must be positive")
        if mode not in ("portfolio", "per_pair"):
            raise ValueError("mode must be portfolio or per_pair")
        if mode == "per_pair" and not symbol:
            raise ValueError("symbol required for per_pair mode")
        return RatchetState(
            account_id=account_id,
            start_equity=float(start_equity),
            equity=float(start_equity),
            mode=mode,
            risk_per_trade_pct=float(risk_per_trade_pct),
            symbol=symbol,
        )

    def _update_pause(self, state: RatchetState) -> None:
        if not state.armed or state.cap <= 0:
            return
        floor = state.cap * (1.0 - self.config.pause_dd_from_cap)
        if state.equity < floor:
            state.paused = True
        elif state.paused and state.equity >= state.cap:
            state.paused = False

    def _apply_lean_cap(self, state: RatchetState, to_eligible: float, to_cap: float) -> tuple[float, float, float]:
        """Clamp CAP to lean ceiling; sweep overflow into eligible (DEAD FREED)."""
        if not self.config.lean_cap_enabled:
            return to_eligible, to_cap, 0.0
        ceiling = self.lean_ceiling_for(state)
        if state.cap <= ceiling + 1e-12:
            return to_eligible, to_cap, 0.0
        overflow = round(state.cap - ceiling, 8)
        state.cap = round(ceiling, 8)
        state.lean_locked = True
        # Sweep overflow into eligible — not left as dead CAP in the broker account
        state.eligible_balance = round(state.eligible_balance + overflow, 8)
        state.dead_freed_total = round(state.dead_freed_total + overflow, 8)
        # retained_profit_total should not claim overflow that was swept out of CAP
        state.retained_profit_total = round(max(0.0, state.retained_profit_total - overflow), 8)
        to_eligible = round(to_eligible + overflow, 8)
        to_cap = round(max(0.0, to_cap - overflow), 8)
        return to_eligible, to_cap, overflow

    def apply_realized_trade(
        self,
        state: RatchetState,
        *,
        trade_id: str,
        realized_pnl: float,
        equity_after: float | None = None,
    ) -> AllocationResult:
        """Apply one closed-trade realized net PnL. Idempotent on trade_id."""
        tid = (trade_id or "").strip()
        if not tid:
            return AllocationResult(False, "missing_trade_id", state=state.snapshot())
        if tid in state.processed_trade_ids:
            return AllocationResult(False, "duplicate_trade_id", state=state.snapshot())

        state.processed_trade_ids.add(tid)
        state.realized_trading_pnl = round(state.realized_trading_pnl + float(realized_pnl), 8)

        if equity_after is not None:
            state.equity = float(equity_after)
        else:
            state.equity = round(state.equity + float(realized_pnl), 8)

        # Arm when equity first reaches threshold
        threshold = self.config.arm_multiple * state.start_equity
        if not state.armed and state.equity >= threshold:
            state.armed = True
            state.cap = round(threshold, 8)
            # If arm threshold already above lean ceiling (huge start equity), clamp immediately
            if self.config.lean_cap_enabled:
                ceiling = self.lean_ceiling_for(state)
                if state.cap > ceiling:
                    state.cap = round(ceiling, 8)
                    state.lean_locked = True

        self._update_pause(state)

        # Losses: equity already updated; CAP unchanged; may pause
        if realized_pnl <= 0:
            self._update_pause(state)
            return AllocationResult(False, "non_profit_trade", state=state.snapshot())

        if not state.armed:
            return AllocationResult(False, "still_compounding", state=state.snapshot())

        if state.paused:
            return AllocationResult(False, "withdrawals_paused_drawdown", state=state.snapshot())

        if state.equity <= state.cap + 1e-12:
            return AllocationResult(False, "equity_not_above_cap", state=state.snapshot())

        excess = round(state.equity - state.cap, 8)
        ceiling = self.lean_ceiling_for(state)

        # Once lean-locked (CAP at ceiling), 100% of excess goes to eligible (zero dead CAP growth)
        if self.config.lean_cap_enabled and state.cap >= ceiling - 1e-9:
            state.lean_locked = True
            to_eligible = excess
            to_cap = 0.0
            state.eligible_balance = round(state.eligible_balance + to_eligible, 8)
            state.dead_freed_total = round(state.dead_freed_total + to_eligible, 8)
            # CAP stays at ceiling
            state.cap = round(ceiling, 8)
            return AllocationResult(
                True,
                "allocated_lean_sweep",
                excess=excess,
                to_eligible=to_eligible,
                to_cap=0.0,
                dead_freed=to_eligible,
                state=state.snapshot(),
            )

        # Growing phase: classic 70/30
        to_eligible = round(excess * self.config.withdraw_pct, 8)
        to_cap = round(excess * self.config.retain_pct, 8)
        state.eligible_balance = round(state.eligible_balance + to_eligible, 8)
        state.cap = round(state.cap + to_cap, 8)
        state.retained_profit_total = round(state.retained_profit_total + to_cap, 8)

        dead_freed = 0.0
        to_eligible, to_cap, dead_freed = self._apply_lean_cap(state, to_eligible, to_cap)
        reason = "allocated_lean_lock" if dead_freed > 0 else "allocated"

        return AllocationResult(
            True,
            reason,
            excess=excess,
            to_eligible=to_eligible,
            to_cap=to_cap,
            dead_freed=dead_freed,
            state=state.snapshot(),
        )

    def request_withdrawal(self, state: RatchetState, amount: float) -> AllocationResult:
        """Move amount from eligible to cumulative_withdrawn (request reservation)."""
        amt = round(float(amount), 8)
        if amt <= 0:
            return AllocationResult(False, "invalid_amount", state=state.snapshot())
        if state.paused:
            return AllocationResult(False, "withdrawals_paused_drawdown", state=state.snapshot())
        if amt > state.eligible_balance + 1e-12:
            return AllocationResult(False, "insufficient_eligible_balance", state=state.snapshot())
        state.eligible_balance = round(state.eligible_balance - amt, 8)
        state.cumulative_withdrawn = round(state.cumulative_withdrawn + amt, 8)
        # Accounting equity reduced when funds leave the trading account
        state.equity = round(state.equity - amt, 8)
        self._update_pause(state)
        return AllocationResult(
            True, "withdrawal_reserved", excess=amt, to_eligible=-amt, state=state.snapshot()
        )


def run_cash_path(
    start_equity: float,
    trade_pnls: list[tuple[str, float]],
    *,
    risk_pct: float = 1.0,
    config: RatchetConfig | None = None,
) -> dict[str, Any]:
    """Helper for tests/backtests: sequence of (trade_id, realized_pnl)."""
    eng = HybridRatchetEngine(config)
    st = eng.seed("TEST", start_equity, risk_per_trade_pct=risk_pct)
    log = []
    for tid, pnl in trade_pnls:
        res = eng.apply_realized_trade(st, trade_id=tid, realized_pnl=pnl)
        log.append({"trade_id": tid, "pnl": pnl, "reason": res.reason, "state": res.state})
    snap = st.snapshot()
    return {
        "final": snap,
        "events": log,
        "total_value": snap["total_value"],
        "max_eligible": snap["eligible_balance"],
        "cumulative_withdrawn": snap["cumulative_withdrawn"],
        "dead_freed_total": snap["dead_freed_total"],
        "cap": snap["cap"],
        "lean_locked": snap["lean_locked"],
    }
