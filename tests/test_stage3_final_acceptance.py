"""Stage 3 final engineering acceptance — no strategy promotion.

Covers:
- controlled_demo gate (not production)
- production_authorized remains false under demo publish
- research/V53/RSI9/Native cannot enter executable queue
- no auto-flip policy on autonomous gate
- Stage 3.3 shared-session contract still present
- Executor source allows CONTROLLED_DEMO both directions
"""
from __future__ import annotations

from pathlib import Path

from app.services.executor_signal_service import ExecutorSignalService


def test_production_authorized_default_false_on_publish():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-S3",
        symbol="EURUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        volume=0.01,
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    row = svc.get_pending("ACC-S3", "EURUSD")
    assert row is not None
    assert row["production_authorized"] is False
    assert row["controlled_demo_authorized"] is True
    assert sid == row["signal_id"]


def test_controlled_demo_buy_and_sell_both_authorized_for_queue():
    """Server queue allows both sides for controlled_demo_test."""
    for side in ("BUY", "SELL"):
        svc = ExecutorSignalService()
        svc.publish(
            account_id="ACC-S3",
            symbol="EURUSD",
            side=side,
            methodology="controlled_demo_test",
            rule_name="controlled_demo_test",
            volume=0.01,
            controlled_demo_authorized=True,
            production_authorized=False,
        )
        row = svc.get_pending("ACC-S3", "EURUSD")
        assert row is not None, side
        assert row["side"] == side
        assert row["production_authorized"] is False


def test_research_strategies_cannot_use_controlled_demo_flag():
    svc = ExecutorSignalService()
    for meth in ("rsi9_transfer", "native_discovery", "v53_6", "v31_short_baseline", "stage3b"):
        svc.publish(
            account_id="ACC-S3",
            symbol="EURUSD",
            side="SELL",
            methodology=meth,
            controlled_demo_authorized=True,
            production_authorized=False,
        )
        assert svc.get_pending("ACC-S3", "EURUSD") is None, meth


def test_generation3_and_transfer_tokens_blocked():
    svc = ExecutorSignalService()
    for meth in ("transfer_x", "research_candidate", "generation3_breakout"):
        svc.publish(
            account_id="ACC-S3",
            symbol="GBPUSD",
            side="BUY",
            methodology=meth,
            production_authorized=True,
            controlled_demo_authorized=True,
        )
        assert svc.get_pending("ACC-S3", "GBPUSD") is None, meth


def test_no_auto_flip_policy_in_autonomous_gate():
    """Autonomous gate rejects same-direction re-entry and flip while position open."""
    from app.services.autonomous_ohlc_signal_service import AutonomousOhlcSignalService

    auto = AutonomousOhlcSignalService()
    auto.set_side("ACC-S3", "EURUSD", "SELL")
    allow, reason = auto.gate_signal("ACC-S3", "EURUSD", "SELL", 0.9, methodology="v53_6")
    assert allow is False
    assert "same_direction" in reason or "open" in reason.lower()
    allow2, reason2 = auto.gate_signal("ACC-S3", "EURUSD", "BUY", 0.9, methodology="v53_6")
    assert allow2 is False
    assert "flip" in reason2 or "buy" in reason2.lower() or "baseline" in reason2.lower()


def test_executor_mq5_allows_controlled_demo_both_directions():
    src = Path("release/desktop/AEGIS_Executor.mq5").read_text()
    assert "CONTROLLED_DEMO" in src
    # CONTROLLED_DEMO branch sets shortOnlyMeth = false
    assert "CONTROLLED_DEMO" in src and "shortOnlyMeth = false" in src


def test_stage33_shared_session_still_wired():
    router = Path("backend/app/api/executor_router.py").read_text()
    assert router.count("session=session") >= 3
    pr = Path("backend/app/services/portfolio_risk_service.py").read_text()
    assert "_apply_open_risk_delta" in pr
    assert "with_for_update" in pr


def test_demo_monitor_publish_sets_controlled_not_production():
    src = Path("backend/app/api/demo_monitor_router.py").read_text()
    assert "controlled_demo_authorized=True" in src
    assert "production_authorized=False" in src
    assert 'methodology="controlled_demo_test"' in src


def test_settings_production_authorized_default_false():
    from app.config import settings
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False
