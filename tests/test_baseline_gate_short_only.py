from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService


def test_baseline_rejects_buy():
    svc = AutonomousOhlcSignalService()
    allow, reason = svc.gate_signal("ACC", "AUDUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert allow is False
    assert "buy" in reason.lower() or "short" in reason.lower()


def test_baseline_allows_sell_when_flat():
    svc = AutonomousOhlcSignalService()
    allow, reason = svc.gate_signal("ACC", "AUDUSD", "SELL", 1.0, methodology="v31_short_baseline")
    assert allow is True
