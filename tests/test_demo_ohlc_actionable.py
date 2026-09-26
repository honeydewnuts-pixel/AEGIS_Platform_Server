"""
Baseline research OHLC path is V31 SHORT / V53.6 — not demo_ohlc_structure.

Slope-based BUY/SELL substitute is disabled. Tests assert that behavior.
"""
from app.services.universal_analysis_service import UniversalAnalysisService


def _bars(n=40, drift=-0.0002):
    bars = []
    c = 1.2500
    for i in range(n):
        o = c
        c = c + drift
        bars.append({
            "time": 1_700_000_000 + i * 300,
            "open": o,
            "high": max(o, c) + 0.0001,
            "low": min(o, c) - 0.0001,
            "close": c,
            "tick_volume": 10,
        })
    return bars


def test_slope_downtrend_does_not_force_demo_sell():
    """Random slope is not the cash-test methodology — may HOLD under V31 filters."""
    svc = UniversalAnalysisService()
    out = svc._evaluate_research_ohlc(
        "GBPUSD", "M5", ("AEGIS-RB-V31-GBPUSD-5M",),
        {"close": 1.24, "bars": _bars(80, -0.0003)},
    )
    assert out is not None
    assert out["signal"] in ("HOLD", "SELL")
    assert out["signal"] != "BUY"
    assert out.get("methodology") == "v31_short_baseline" or "V31" in str(out.get("rule_name") or "")


def test_slope_uptrend_never_emits_buy_on_baseline():
    svc = UniversalAnalysisService()
    out = svc._evaluate_research_ohlc(
        "AUDUSD", "M5", ("AEGIS-RB-V53.6-V31-AUDUSD-5M",),
        {"close": 0.67, "bars": _bars(80, 0.0003)},
    )
    assert out is not None
    assert out["signal"] != "BUY"
    assert out["signal"] in ("HOLD", "SELL")
