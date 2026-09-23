"""Unit-level checks for notification helpers (no DB required)."""

from app.services.notification_service import ACTIONABLE_SIGNALS, DEFAULT_MIN_CONFIDENCE_EXTERNAL


def test_actionable_signals():
    assert "BUY" in ACTIONABLE_SIGNALS
    assert "SELL" in ACTIONABLE_SIGNALS
    assert "HOLD" not in ACTIONABLE_SIGNALS


def test_default_min_confidence():
    assert DEFAULT_MIN_CONFIDENCE_EXTERNAL == 0.55
