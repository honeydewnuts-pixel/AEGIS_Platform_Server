"""Fail-closed autonomous execution — no legacy lot fallback."""
import asyncio
import pytest

from app.services.autonomous_execution_service import AutonomousDemoExecutionService


class _PR:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def size_order(self, *a, **k):
        self.calls.append((a, k))
        return self.response


class _Sub:
    async def get_status(self, account_id):
        return {"plan": "demo", "risk_preset": "standard"}


def test_rejects_without_entry_stop():
    svc = AutonomousDemoExecutionService(subscription_service=_Sub())
    svc.portfolio_risk = _PR({"allow": True, "volume": 0.1})
    out = asyncio.get_event_loop().run_until_complete(
        svc.execute_if_signal(
            account_id="A1",
            symbol="USDCHF",
            result={"signal": "SELL"},
            market_snapshot={},
        )
    )
    assert out["executed"] is False
    assert out["reason"] == "entry_or_stop_missing_for_sizing"
    assert out["volume"] == 0.0


def test_rejects_when_sizing_disallows():
    svc = AutonomousDemoExecutionService(subscription_service=_Sub())
    pr = _PR({"allow": False, "reason": "min_lot_exceeds_risk_budget", "volume": 0})
    svc.portfolio_risk = pr
    out = asyncio.get_event_loop().run_until_complete(
        svc.execute_if_signal(
            account_id="A1",
            symbol="USDCHF",
            result={
                "signal": "SELL",
                "entry_price": 0.9,
                "stop_loss": 0.9015,
                "atr14": 0.001,
            },
        )
    )
    assert out["executed"] is False
    assert out["reason"] == "min_lot_exceeds_risk_budget"
    assert out["volume"] == 0.0
    assert pr.calls
    # Must have passed entry/stop/side
    kwargs = pr.calls[0][1]
    assert kwargs["entry_price"] == 0.9
    assert kwargs["stop_loss"] == 0.9015
    assert kwargs["side"] == "SELL"


def test_rejects_zero_volume_even_if_allow_true():
    svc = AutonomousDemoExecutionService(subscription_service=_Sub())
    svc.portfolio_risk = _PR({"allow": True, "volume": 0})
    out = asyncio.get_event_loop().run_until_complete(
        svc.execute_if_signal(
            account_id="A1",
            symbol="USDCHF",
            result={"signal": "SELL", "entry_price": 0.9, "stop_loss": 0.9015},
        )
    )
    assert out["executed"] is False
    assert out["reason"] == "invalid_volume_after_sizing"


def test_no_portfolio_risk_service():
    svc = AutonomousDemoExecutionService(subscription_service=_Sub())
    svc.portfolio_risk = None
    out = asyncio.get_event_loop().run_until_complete(
        svc.execute_if_signal(
            account_id="A1",
            symbol="USDCHF",
            result={"signal": "SELL", "entry_price": 0.9, "stop_loss": 0.9015},
        )
    )
    assert out["executed"] is False
    assert out["reason"] == "portfolio_risk_unavailable"


def test_successful_size_still_needs_backend():
    """Sizing ok but no worker → not executed; volume is sized (not legacy 0.01)."""
    svc = AutonomousDemoExecutionService(subscription_service=_Sub())
    svc.portfolio_risk = _PR({"allow": True, "volume": 0.37})
    out = asyncio.get_event_loop().run_until_complete(
        svc.execute_if_signal(
            account_id="A1",
            symbol="USDCHF",
            result={"signal": "SELL", "entry_price": 0.9, "stop_loss": 0.9015},
        )
    )
    assert out["volume"] == 0.37
    assert out["executed"] is False
    assert out["reason"] == "no_execution_backend"
