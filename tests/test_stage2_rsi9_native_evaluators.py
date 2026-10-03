"""
Stage 2 acceptance tests: RSI9 transfer + native discovery evaluators,
registry loading, autonomous gate direction policy, V53.6 regression.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]


def _synthetic_bars(n: int = 80, seed: int = 42, trend: float = 0.0) -> list[dict]:
    rng = np.random.default_rng(seed)
    mid = 1.1000
    bars = []
    for i in range(n):
        mid = mid + trend + float(rng.normal(0, 0.0003))
        o = mid
        h = mid + abs(float(rng.normal(0, 0.0002)))
        l = mid - abs(float(rng.normal(0, 0.0002)))
        c = mid + float(rng.normal(0, 0.0001))
        bars.append({"open": o, "high": h, "low": l, "close": c})
    return bars


def _bars_rsi_overbought(n: int = 60) -> list[dict]:
    """Force RSI(9) high at the end by a sharp run-up."""
    bars = _synthetic_bars(n - 10, seed=7, trend=-0.0001)
    last = bars[-1]["close"]
    for i in range(10):
        last = last + 0.0015
        bars.append(
            {
                "open": last - 0.0002,
                "high": last + 0.0003,
                "low": last - 0.0004,
                "close": last,
            }
        )
    return bars


# ---------------------------------------------------------------------------
# Rulebook loading
# ---------------------------------------------------------------------------


def test_rsi9_rulebooks_load():
    from app.rulebooks.evaluators.rsi9_short_transfer import load_rsi9_rulebook

    for inst in ("USDCHF", "EURUSD", "GBPUSD", "NZDJPY", "BTCUSD"):
        rb = load_rsi9_rulebook(inst, repo_root=REPO)
        assert rb is not None, f"missing RSI9 rulebook for {inst}"
        assert rb.get("production_authorized") is not True
        # Forex transfer packs include entry; alt/crypto may use defaults in evaluator
        if inst not in ("BTCUSD", "ETHUSD"):
            assert "entry" in rb


def test_native_rulebooks_load():
    from app.rulebooks.evaluators.native_discovery import load_native_rulebook

    for inst in ("USDJPY", "GER40", "UK100", "US100", "UKOIL", "XAGUSD"):
        rb = load_native_rulebook(inst, repo_root=REPO)
        assert rb is not None, f"missing native rulebook for {inst}"
        assert rb.get("production_authorized") is not True


def test_missing_rulebook_fails_safe():
    from app.rulebooks.evaluators.rsi9_short_transfer import load_rsi9_rulebook, evaluate_rsi9_short_from_bars
    from app.rulebooks.evaluators.native_discovery import load_native_rulebook, evaluate_native_from_bars

    assert load_rsi9_rulebook("NOSUCHPAIR", repo_root=REPO) is None
    assert load_native_rulebook("NOSUCHPAIR", repo_root=REPO) is None

    out = evaluate_rsi9_short_from_bars(_synthetic_bars(), instrument="NOSUCHPAIR", rulebook=None)
    assert out["signal"] == "HOLD"
    assert out["methodology"] == "rsi9_transfer"

    out2 = evaluate_native_from_bars(_synthetic_bars(), instrument="NOSUCHPAIR", rulebook=None)
    assert out2["signal"] == "HOLD"
    assert out2["methodology"] == "native_discovery"


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def test_rsi9_insufficient_bars_hold():
    from app.rulebooks.evaluators.rsi9_short_transfer import evaluate_rsi9_short_from_bars, load_rsi9_rulebook

    rb = load_rsi9_rulebook("USDCHF", repo_root=REPO)
    out = evaluate_rsi9_short_from_bars([{"close": 1.0}] * 5, instrument="USDCHF", rulebook=rb)
    assert out["signal"] == "HOLD"
    assert out["confidence"] == 0.0


def test_rsi9_overbought_can_sell():
    from app.rulebooks.evaluators.rsi9_short_transfer import evaluate_rsi9_short_from_bars, load_rsi9_rulebook

    rb = load_rsi9_rulebook("USDCHF", repo_root=REPO)
    bars = _bars_rsi_overbought()
    out = evaluate_rsi9_short_from_bars(bars, instrument="USDCHF", rulebook=rb)
    assert out["methodology"] == "rsi9_transfer"
    assert out["strategy_id"] == "rsi9_transfer"
    assert out["production_authorized"] is False
    assert out["signal"] in ("HOLD", "SELL")
    # With forced run-up, expect SELL most of the time
    assert out["signal"] == "SELL", out


def test_rsi9_never_buy():
    from app.rulebooks.evaluators.rsi9_short_transfer import evaluate_rsi9_short_from_bars, load_rsi9_rulebook

    rb = load_rsi9_rulebook("EURUSD", repo_root=REPO)
    for seed in range(5):
        out = evaluate_rsi9_short_from_bars(
            _synthetic_bars(80, seed=seed), instrument="EURUSD", rulebook=rb
        )
        assert out["signal"] != "BUY"


def test_native_evaluates_without_crash():
    from app.rulebooks.evaluators.native_discovery import evaluate_native_from_bars, load_native_rulebook

    rb = load_native_rulebook("USDJPY", repo_root=REPO)
    out = evaluate_native_from_bars(_synthetic_bars(100), instrument="USDJPY", rulebook=rb)
    assert out["methodology"] == "native_discovery"
    assert out["strategy_id"] == "native_discovery"
    assert out["signal"] in ("HOLD", "BUY", "SELL")


# ---------------------------------------------------------------------------
# Universal analysis priority routing
# ---------------------------------------------------------------------------


def test_universal_prefers_rsi9_over_v31():
    from app.services.universal_analysis_service import UniversalAnalysisService

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    bars = _bars_rsi_overbought()
    snap = {"close": bars[-1]["close"], "bars": bars}
    out = svc._evaluate_research_ohlc("USDCHF", "M5", ["AEGIS-RB-V53.6-V31-USDCHF-5M"], snap)
    assert out is not None
    assert out.get("methodology") == "rsi9_transfer"
    assert out.get("strategy_id") == "rsi9_transfer"


def test_universal_native_for_usdjpy():
    from app.services.universal_analysis_service import UniversalAnalysisService

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    bars = _synthetic_bars(100)
    snap = {"close": bars[-1]["close"], "bars": bars}
    out = svc._evaluate_research_ohlc("USDJPY", "M5", [], snap)
    assert out is not None
    assert out.get("methodology") == "native_discovery"


# ---------------------------------------------------------------------------
# Autonomous gate — direction policy
# ---------------------------------------------------------------------------


def test_gate_v31_rejects_buy():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-1", "EURUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert ok is False
    assert "buy_rejected" in reason or "short_only" in reason


def test_gate_rsi9_allows_sell():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-1", "USDCHF", "SELL", 1.0, methodology="rsi9_transfer")
    assert ok is True
    assert "rsi9" in reason


def test_gate_rsi9_rejects_buy():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-1", "USDCHF", "BUY", 1.0, methodology="rsi9_transfer")
    assert ok is False


def test_gate_native_allows_buy_and_sell():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok_b, r_b = svc.gate_signal("ACC-1", "USDJPY", "BUY", 1.0, methodology="native_discovery")
    ok_s, r_s = svc.gate_signal("ACC-2", "USDJPY", "SELL", 1.0, methodology="native_discovery")
    assert ok_b is True
    assert ok_s is True


def test_gate_dedupe_same_direction():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    svc.set_side("ACC-1", "USDCHF", "SELL")
    ok, reason = svc.gate_signal("ACC-1", "USDCHF", "SELL", 1.0, methodology="rsi9_transfer")
    assert ok is False
    assert "same_direction" in reason


# ---------------------------------------------------------------------------
# Incomplete candle / empty bars
# ---------------------------------------------------------------------------


def test_empty_bars_hold():
    from app.services.universal_analysis_service import UniversalAnalysisService

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    out = svc._evaluate_research_ohlc("EURUSD", "M5", [], {"close": 1.1, "bars": []})
    assert out["signal"] == "HOLD"
    assert out["confidence"] == 0.0


def test_native_long_rulebooks_present():
    from pathlib import Path
    import json
    root = Path(__file__).resolve().parents[1]
    native = root / "registry" / "v40" / "rulebooks_native"
    for sym in ["AUDUSD", "EURUSD", "GBPUSD", "USDCHF", "USDJPY"]:
        p = native / f"{sym}.json"
        assert p.exists(), f"missing {p}"
        d = json.loads(p.read_text())
        assert d.get("production_authorized") is False
