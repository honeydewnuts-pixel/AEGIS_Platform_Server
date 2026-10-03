"""
Stage 2 / Stage 2B integration acceptance tests.

Validates RSI9 SHORT + Native LONG coexistence, frozen parameters,
production_authorized=false, V53.6 isolation, exit metadata handoff,
and screenshot isolation flags.

Does NOT retune strategies or promote production authorization.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]

FOREX_12 = [
    "AUDUSD",
    "EURCHF",
    "EURGBP",
    "EURJPY",
    "EURUSD",
    "GBPJPY",
    "GBPNZD",
    "GBPUSD",
    "NZDCHF",
    "NZDJPY",
    "USDCAD",
    "USDCHF",
]

FROZEN_LONG = {
    "entry_name": "long_ema_pullback",
    "stop_atr": 1.0,
    "trail_atr": 0.5,
    "max_hold_bars": 72,
    "source_contains": "USDJPY",
}


def _synthetic_bars(n: int = 80, seed: int = 42, trend: float = 0.0) -> list[dict]:
    rng = np.random.default_rng(seed)
    mid = 1.1000
    bars = []
    for _ in range(n):
        mid = mid + trend + float(rng.normal(0, 0.0003))
        bars.append(
            {
                "open": mid,
                "high": mid + abs(float(rng.normal(0, 0.0002))),
                "low": mid - abs(float(rng.normal(0, 0.0002))),
                "close": mid + float(rng.normal(0, 0.0001)),
            }
        )
    return bars


def _bars_rsi_overbought(n: int = 60) -> list[dict]:
    bars = _synthetic_bars(n - 12, seed=7, trend=-0.00005)
    last = bars[-1]["close"]
    for _ in range(12):
        last = last + 0.0020
        bars.append(
            {
                "open": last - 0.0002,
                "high": last + 0.0003,
                "low": last - 0.0004,
                "close": last,
            }
        )
    return bars


def _bars_uptrend_pullback(n: int = 100) -> list[dict]:
    """Uptrend then pullback toward EMA20 — favors long_ema_pullback."""
    bars = []
    mid = 1.05
    for i in range(n - 5):
        mid += 0.0008
        bars.append(
            {
                "open": mid - 0.0001,
                "high": mid + 0.0003,
                "low": mid - 0.0003,
                "close": mid,
            }
        )
    for _ in range(5):
        mid -= 0.0006
        bars.append(
            {
                "open": mid + 0.0002,
                "high": mid + 0.0003,
                "low": mid - 0.0004,
                "close": mid,
            }
        )
    return bars


@pytest.mark.parametrize("sym", FOREX_12)
def test_native_long_rulebook_content(sym):
    from app.rulebooks.evaluators.native_discovery import load_native_rulebook

    rb = load_native_rulebook(sym, repo_root=REPO)
    assert rb is not None, f"{sym}: rulebook missing"
    assert rb.get("production_authorized") is False
    assert str(rb.get("status", "")).startswith("RESEARCH") or rb.get("qualified_with_test") is True
    entry = rb.get("entry") or {}
    assert entry.get("name") == FROZEN_LONG["entry_name"]
    assert entry.get("side") == "long"
    assert "LONG" in str(rb.get("direction", "")).upper()
    exit_cfg = rb.get("exit") or {}
    assert float(exit_cfg.get("initial_stop_atr")) == FROZEN_LONG["stop_atr"]
    assert float(exit_cfg.get("trailing_stop_atr")) == FROZEN_LONG["trail_atr"]
    assert int(exit_cfg.get("max_hold_bars")) == FROZEN_LONG["max_hold_bars"]
    assert FROZEN_LONG["source_contains"] in str(rb.get("source_transfer") or rb.get("rulebook_id") or "")


@pytest.mark.parametrize("sym", FOREX_12)
def test_rsi9_forex_rulebook_content(sym):
    from app.rulebooks.evaluators.rsi9_short_transfer import load_rsi9_rulebook

    rb = load_rsi9_rulebook(sym, repo_root=REPO)
    assert rb is not None, f"{sym}: RSI9 rulebook missing"
    assert rb.get("production_authorized") is False


def test_rsi9_crypto_books_present():
    from app.rulebooks.evaluators.rsi9_short_transfer import load_rsi9_rulebook

    for inst in ("BTCUSD", "ETHUSD"):
        rb = load_rsi9_rulebook(inst, repo_root=REPO)
        assert rb is not None
        assert rb.get("production_authorized") is not True


def test_rsi9_never_buy():
    from app.rulebooks.evaluators.rsi9_short_transfer import evaluate_rsi9_short_from_bars

    out = evaluate_rsi9_short_from_bars(_bars_rsi_overbought(), instrument="USDCHF")
    assert str(out.get("signal")).upper() in ("HOLD", "SELL")
    assert str(out.get("signal")).upper() != "BUY"
    assert out.get("methodology") == "rsi9_transfer"
    assert out.get("production_authorized") is False


def test_native_can_buy_on_pullback():
    from app.rulebooks.evaluators.native_discovery import evaluate_native_from_bars, load_native_rulebook

    rb = load_native_rulebook("EURUSD", repo_root=REPO)
    assert rb is not None
    out = evaluate_native_from_bars(_bars_uptrend_pullback(), instrument="EURUSD", rulebook=rb)
    assert str(out.get("signal")).upper() in ("HOLD", "BUY")
    assert out.get("methodology") == "native_discovery"
    assert out.get("production_authorized") is False
    ep = out.get("exit_params") or {}
    assert int(ep.get("max_hold_bars") or 0) == 72
    assert float(ep.get("stop_atr") or 0) == 1.0


def test_v31_short_rejects_buy_gate():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-T", "EURUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert ok is False
    assert "buy" in reason.lower() or "short" in reason.lower()


def test_rsi9_gate_rejects_buy():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-T", "EURUSD", "BUY", 1.0, methodology="rsi9_transfer")
    assert ok is False


def test_native_gate_allows_buy():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    ok, reason = svc.gate_signal("ACC-T", "EURUSD", "BUY", 1.0, methodology="native_discovery")
    assert ok is True, reason


def test_native_gate_no_auto_flip():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = AutonomousOhlcSignalService()
    svc.set_side("ACC-T", "EURUSD", "SELL")
    ok, reason = svc.gate_signal("ACC-T", "EURUSD", "BUY", 1.0, methodology="native_discovery")
    assert ok is False
    assert "flip" in reason.lower() or "same" in reason.lower()


def test_coexistence_rsi9_hold_native_can_route(monkeypatch):
    """RSI9 HOLD must not block native path when native is actionable."""
    from app.services.universal_analysis_service import UniversalAnalysisService
    import app.rulebooks.evaluators.rsi9_short_transfer as rsi9_mod
    import app.rulebooks.evaluators.native_discovery as nat_mod

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    bars = _bars_uptrend_pullback()
    snap = {"close": bars[-1]["close"], "bars": bars}

    def fake_rsi9(*a, **k):
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "production_authorized": False,
            "rulebook_id": "fake-rsi9",
            "exit_params": {"stop_atr": 1.0, "trail_atr": 0.5, "max_hold_bars": 72},
        }

    def fake_native(*a, **k):
        return {
            "signal": "BUY",
            "confidence": 1.0,
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "production_authorized": False,
            "rulebook_id": "fake-native",
            "exit_params": {"stop_atr": 1.0, "trail_atr": 0.5, "max_hold_bars": 72, "break_even_at_r": 1.0},
            "indicators": {"atr14": 0.001},
        }

    monkeypatch.setattr(rsi9_mod, "evaluate_rsi9_short_from_bars", fake_rsi9)
    monkeypatch.setattr(rsi9_mod, "load_rsi9_rulebook", lambda *a, **k: {"rulebook_id": "fake-rsi9"})
    monkeypatch.setattr(nat_mod, "evaluate_native_from_bars", fake_native)
    monkeypatch.setattr(nat_mod, "load_native_rulebook", lambda *a, **k: {"rulebook_id": "fake-native"})

    out = svc._evaluate_research_ohlc("EURUSD", "M5", [], snap)
    assert out is not None
    assert str(out.get("signal")).upper() == "BUY"
    assert out.get("methodology") == "native_discovery"
    assert int(out.get("max_hold_bars") or 0) == 72
    assert float(out.get("initial_stop_atr_mult") or 0) == 1.0
    assert out.get("take_profit") is None
    assert out.get("production_authorized") is False


def test_coexistence_rsi9_sell_preferred_over_native_buy(monkeypatch):
    """Existing policy: actionable RSI9 SELL wins over concurrent Native BUY."""
    from app.services.universal_analysis_service import UniversalAnalysisService
    import app.rulebooks.evaluators.rsi9_short_transfer as rsi9_mod
    import app.rulebooks.evaluators.native_discovery as nat_mod

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    bars = _synthetic_bars(80)
    snap = {"close": bars[-1]["close"], "bars": bars}

    monkeypatch.setattr(
        rsi9_mod,
        "evaluate_rsi9_short_from_bars",
        lambda *a, **k: {
            "signal": "SELL",
            "confidence": 1.0,
            "methodology": "rsi9_transfer",
            "strategy_id": "rsi9_transfer",
            "production_authorized": False,
            "rulebook_id": "fake-rsi9",
            "exit_params": {"stop_atr": 1.0, "trail_atr": 0.5, "max_hold_bars": 72},
        },
    )
    monkeypatch.setattr(rsi9_mod, "load_rsi9_rulebook", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(
        nat_mod,
        "evaluate_native_from_bars",
        lambda *a, **k: {
            "signal": "BUY",
            "confidence": 1.0,
            "methodology": "native_discovery",
            "strategy_id": "native_discovery",
            "production_authorized": False,
            "rulebook_id": "fake-native",
            "exit_params": {"stop_atr": 1.0, "trail_atr": 0.5, "max_hold_bars": 72},
        },
    )
    monkeypatch.setattr(nat_mod, "load_native_rulebook", lambda *a, **k: {"x": 1})

    out = svc._evaluate_research_ohlc("EURUSD", "M5", [], snap)
    assert str(out.get("signal")).upper() == "SELL"
    assert out.get("methodology") == "rsi9_transfer"


def test_both_hold_not_executable(monkeypatch):
    from app.services.universal_analysis_service import UniversalAnalysisService
    import app.rulebooks.evaluators.rsi9_short_transfer as rsi9_mod
    import app.rulebooks.evaluators.native_discovery as nat_mod
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    svc = UniversalAnalysisService.__new__(UniversalAnalysisService)
    bars = _synthetic_bars(50)
    snap = {"close": bars[-1]["close"], "bars": bars}
    hold = {
        "signal": "HOLD",
        "confidence": 0.0,
        "methodology": "rsi9_transfer",
        "strategy_id": "rsi9_transfer",
        "production_authorized": False,
        "exit_params": {"stop_atr": 1.0, "trail_atr": 0.5, "max_hold_bars": 72},
    }
    monkeypatch.setattr(rsi9_mod, "evaluate_rsi9_short_from_bars", lambda *a, **k: hold)
    monkeypatch.setattr(rsi9_mod, "load_rsi9_rulebook", lambda *a, **k: {"x": 1})
    monkeypatch.setattr(
        nat_mod,
        "evaluate_native_from_bars",
        lambda *a, **k: {**hold, "methodology": "native_discovery", "strategy_id": "native_discovery"},
    )
    monkeypatch.setattr(nat_mod, "load_native_rulebook", lambda *a, **k: {"x": 1})
    out = svc._evaluate_research_ohlc("EURUSD", "M5", [], snap)
    assert str(out.get("signal")).upper() == "HOLD"
    gate = AutonomousOhlcSignalService()
    ok, _ = gate.gate_signal("A", "EURUSD", "HOLD", 0.0, methodology=out.get("methodology"))
    assert ok is False


def test_screenshot_publish_flags_default_false():
    from app.config import settings

    assert getattr(settings, "SCREENSHOT_PUBLISHES_TO_EXECUTOR", False) is False
    assert getattr(settings, "SCREENSHOT_TRIGGERS_WORKER_EXECUTION", False) is False


def test_generate_12_pair_acceptance_matrix():
    from app.rulebooks.evaluators.rsi9_short_transfer import load_rsi9_rulebook
    from app.rulebooks.evaluators.native_discovery import load_native_rulebook

    rows = []
    for sym in FOREX_12:
        rsi = load_rsi9_rulebook(sym, repo_root=REPO)
        nat = load_native_rulebook(sym, repo_root=REPO)
        entry = (nat or {}).get("entry") or {}
        exit_cfg = (nat or {}).get("exit") or {}
        param_ok = (
            nat is not None
            and entry.get("name") == "long_ema_pullback"
            and float(exit_cfg.get("initial_stop_atr") or 0) == 1.0
            and float(exit_cfg.get("trailing_stop_atr") or 0) == 0.5
            and int(exit_cfg.get("max_hold_bars") or 0) == 72
        )
        rows.append(
            {
                "pair": sym,
                "rsi9_book": bool(rsi),
                "native_book": bool(nat),
                "rsi9_load": "OK" if rsi else "FAIL",
                "native_load": "OK" if nat else "FAIL",
                "rsi9_direction": (rsi or {}).get("direction"),
                "native_direction": (nat or {}).get("direction"),
                "rsi9_auth": (rsi or {}).get("production_authorized"),
                "native_auth": (nat or {}).get("production_authorized"),
                "parameter_match": param_ok,
                "routing": "dual_eval_rsi9_then_native",
                "risk": "shared_portfolio_risk",
                "execution_gate": "methodology_specific",
            }
        )
    out = REPO / "docs" / "STAGE2B_12_PAIR_ACCEPTANCE_MATRIX.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    assert all(r["rsi9_book"] and r["native_book"] and r["parameter_match"] for r in rows)
    assert all(r["rsi9_auth"] is False and r["native_auth"] is False for r in rows)
