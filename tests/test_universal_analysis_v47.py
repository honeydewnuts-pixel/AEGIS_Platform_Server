"""V47 universal analysis path — no V3 indicator requirement for V40 pairs."""
from app.services.universal_analysis_service import UniversalAnalysisService


def test_gbpusd_research_no_indicator_gate():
    u = UniversalAnalysisService()
    r = u.analyze(instrument="GBPUSD", timeframe="M5")
    assert r["signal"] == "HOLD"
    assert r["rule_name"] != "indicators_not_detected"
    assert r.get("router_state") == "ROUTABLE_RESEARCH"
    assert r.get("production_authorized") is False
    assert "rulebook_ids" in r


def test_eurusd_fail_closed():
    u = UniversalAnalysisService()
    r = u.analyze(instrument="EURUSD", timeframe="M5")
    assert r["signal"] == "HOLD"
    assert r["rule_name"] != "indicators_not_detected"
    assert r.get("router_state") == "TRADING_DISABLED"


def test_empty_instrument():
    u = UniversalAnalysisService()
    r = u.analyze(instrument="", timeframe="M5")
    assert r["rule_name"] == "instrument_unspecified"
