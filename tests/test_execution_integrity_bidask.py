"""
Execution integrity — directional Bid/Ask unit tests.

Broker-correct invariants (operational):
  LONG  OPEN  = ASK     LONG  CLOSE = BID
  SHORT OPEN  = BID     SHORT CLOSE = ASK

These tests prove the *reference model* and document deviations in research
artifacts. They do NOT retune strategies or alter frozen V53.6 reconstruction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Reference broker-correct fill model (deterministic)
# ---------------------------------------------------------------------------


def broker_long_entry(ask_open: float) -> float:
    return float(ask_open)


def broker_long_exit(bid_price: float) -> float:
    return float(bid_price)


def broker_short_entry(bid_open: float) -> float:
    return float(bid_open)


def broker_short_exit(ask_price: float) -> float:
    return float(ask_price)


def test_long_entry_is_ask():
    ask, bid = 1.10050, 1.10030
    assert broker_long_entry(ask) == ask
    assert broker_long_entry(ask) != bid


def test_long_exit_is_bid():
    ask, bid = 1.10100, 1.10080
    assert broker_long_exit(bid) == bid
    assert broker_long_exit(bid) != ask


def test_short_entry_is_bid():
    ask, bid = 1.10050, 1.10030
    assert broker_short_entry(bid) == bid
    assert broker_short_entry(bid) != ask


def test_short_exit_is_ask():
    ask, bid = 1.09950, 1.09930
    assert broker_short_exit(ask) == ask
    assert broker_short_exit(ask) != bid


def test_long_stop_uses_bid_touch():
    """LONG stop below entry: triggers when BidLow <= stop; exit at stop/BID."""
    entry = 1.10050  # ask
    stop = 1.09950
    bid_low = 1.09940
    bid_high = 1.10060
    assert bid_low <= stop  # stop hit on bid side
    exit_px = broker_long_exit(stop)  # model: fill at stop on bid
    pnl = exit_px - entry
    assert pnl < 0


def test_short_stop_uses_ask_touch():
    """SHORT stop above entry: triggers when AskHigh >= stop; exit at stop/ASK."""
    entry = 1.10030  # bid
    stop = 1.10130
    ask_high = 1.10140
    assert ask_high >= stop
    exit_px = broker_short_exit(stop)
    pnl = entry - exit_px
    assert pnl < 0


def test_spread_penalizes_round_trip():
    """Zero-edge round trip loses the spread under broker-correct fills."""
    bid_open, ask_open = 1.1000, 1.1002
    bid_close, ask_close = 1.1000, 1.1002  # flat mid
    # Long open ask, close bid
    long_pnl = broker_long_exit(bid_close) - broker_long_entry(ask_open)
    # Short open bid, close ask
    short_pnl = broker_short_entry(bid_open) - broker_short_exit(ask_close)
    assert long_pnl < 0
    assert short_pnl < 0
    assert abs(long_pnl - (-0.0002)) < 1e-12
    assert abs(short_pnl - (-0.0002)) < 1e-12


def test_zero_spread_control_flat():
    bid = ask = 1.1000
    assert broker_long_exit(bid) - broker_long_entry(ask) == 0.0
    assert broker_short_entry(bid) - broker_short_exit(ask) == 0.0


# ---------------------------------------------------------------------------
# Documented research convention vs broker-correct (audit probes)
# ---------------------------------------------------------------------------


def test_rsi9_rulebook_documents_ask_open_short_entry():
    """USDCHF RSI9 research specified next_bar_ask_open — not broker SHORT OPEN=BID."""
    p = REPO / "registry/v40/rulebooks_rsi9_short/USDCHF.json"
    d = json.loads(p.read_text())
    assert (d.get("entry") or {}).get("entry_timing") == "next_bar_ask_open"
    assert d.get("status") == "INVALIDATED_EXECUTION_MODEL_ERROR"
    assert d.get("production_authorized") is False


def test_all_rsi9_forex_use_ask_open_entry_timing():
    root = REPO / "registry/v40/rulebooks_rsi9_short"
    for p in root.glob("*.json"):
        if p.name in ("BTCUSD.json", "ETHUSD.json"):
            continue
        d = json.loads(p.read_text())
        timing = (d.get("entry") or {}).get("entry_timing")
        assert timing == "next_bar_ask_open", f"{p.name}: {timing}"


def test_v53_6_historical_short_uses_ask_open_reconstruction():
    """Frozen V53.6 reconstruction deliberately uses next-bar AskOpen for SHORT."""
    p = REPO / "registry/v53_6/USDCHF/rulebook.json"
    d = json.loads(p.read_text())
    assert d.get("direction") == "SHORT"
    assert "AskOpen" in str((d.get("execution") or {}).get("entry", ""))
    # Must not be production-authorized by governance
    gov = d.get("governance") or {}
    assert gov.get("production_authorization") is False or d.get("production_authorized") is not True


def test_live_executor_sell_uses_bid():
    """Operational Executor: SELL at BID (broker-correct SHORT OPEN)."""
    src = (REPO / "release/desktop/AEGIS_Executor.mq5").read_text(encoding="utf-8", errors="replace")
    assert "ORDER_TYPE_SELL" in src
    assert "SYMBOL_BID" in src
    # BUY at ASK
    assert "ORDER_TYPE_BUY" in src
    assert "SYMBOL_ASK" in src


def test_v31_live_documents_historical_entry_side():
    src = (REPO / "backend/app/rulebooks/live_v31_short.py").read_text()
    assert "AskOpen_next_bar" in src or "entry_side" in src


def test_live_short_manager_stop_on_bid_high():
    """Historical/live short manager stops on BidHigh (V53.6 reconstruction)."""
    from app.rulebooks.live_short_position_manager import BarOHLC, ShortPositionState, step_short_bar

    st = ShortPositionState(
        signal_id="t1",
        symbol="USDCHF",
        entry_price=1.1000,
        initial_risk=0.0010,
        atr_at_signal=0.0005,
        entry_bar_index=0,
    )
    # BidHigh pierces stop 1.1010
    bar = BarOHLC(high=1.1015, low=1.0990, close=1.1005, atr=0.0005)
    out = step_short_bar(st, bar, 1)
    assert out.closed
    assert out.close_reason == "STOP"
    assert out.exit_price == pytest.approx(1.1010)


def test_native_long_books_not_auto_invalidated():
    root = REPO / "registry/v40/rulebooks_native"
    for sym in ("AUDUSD", "EURUSD", "USDCHF", "USDJPY"):
        p = root / f"{sym}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text())
        assert d.get("status") != "INVALIDATED_EXECUTION_MODEL_ERROR"
        assert d.get("production_authorized") is False


def test_production_auth_false_on_rsi9_and_native():
    for folder in ("rulebooks_rsi9_short", "rulebooks_native"):
        root = REPO / "registry/v40" / folder
        for p in root.glob("*.json"):
            d = json.loads(p.read_text())
            assert d.get("production_authorized") is not True, p.name
