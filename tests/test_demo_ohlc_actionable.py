"""Demo OHLC path must emit BUY/SELL so Executor can trade demo accounts."""
from app.services.universal_analysis_service import UniversalAnalysisService


def _bars(n=40, drift=-0.0002):
    bars = []
    c = 1.2500
    for i in range(n):
        o = c
        c = c + drift
        bars.append({"time": 1_700_000_000 + i * 300, "open": o, "high": max(o, c) + 0.0001,
                     "low": min(o, c) - 0.0001, "close": c, "tick_volume": 10})
    return bars


def test_downtrend_emits_sell():
    svc = UniversalAnalysisService()
    out = svc._evaluate_research_ohlc(
        "GBPUSD", "M5", ("AEGIS-RB-V35-GBPUSD-5M",),
        {"close": 1.24, "bars": _bars(40, -0.0003)},
    )
    assert out is not None
    assert out["signal"] == "SELL"
    assert float(out["confidence"]) >= 0.55


def test_uptrend_emits_buy():
    svc = UniversalAnalysisService()
    out = svc._evaluate_research_ohlc(
        "AUDUSD", "M5", (),
        {"close": 0.67, "bars": _bars(40, 0.0003)},
    )
    assert out is not None
    assert out["signal"] == "BUY"
    assert float(out["confidence"]) >= 0.55
