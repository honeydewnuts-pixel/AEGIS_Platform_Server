"""Screenshot analysis must not authorize Executor trades by default."""
from app.config import Settings


def test_screenshot_publish_flags_default_off():
    s = Settings()
    assert getattr(s, "SCREENSHOT_PUBLISHES_TO_EXECUTOR", True) is False
    assert getattr(s, "SCREENSHOT_TRIGGERS_WORKER_EXECUTION", True) is False


def test_baseline_gate_still_short_only():
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService
    svc = AutonomousOhlcSignalService()
    allow, reason = svc.gate_signal("A", "GBPUSD", "BUY", 1.0, methodology="v31_short_baseline")
    assert allow is False
    allow2, _ = svc.gate_signal("A", "GBPUSD", "SELL", 1.0, methodology="v31_short_baseline")
    assert allow2 is True
