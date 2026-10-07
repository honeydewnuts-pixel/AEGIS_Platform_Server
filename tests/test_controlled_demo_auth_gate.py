"""Controlled Demo path is separate from production_authorized."""
from app.services.executor_signal_service import ExecutorSignalService


def test_production_false_blocked():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        methodology="controlled_demo_test",
        production_authorized=False,
        controlled_demo_authorized=False,
    )
    assert sid
    assert svc.get_pending("ACC-1", "EURUSD") is None


def test_controlled_demo_authorized_passes():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        volume=0.01,
        production_authorized=False,
        controlled_demo_authorized=True,
    )
    assert sid
    row = svc.get_pending("ACC-1", "EURUSD")
    assert row is not None
    assert row["signal_id"] == sid
    assert row["production_authorized"] is False
    assert row["controlled_demo_authorized"] is True
    assert row["methodology"] == "controlled_demo_test"


def test_controlled_demo_cannot_carry_research_methodology():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        methodology="rsi9_transfer",
        production_authorized=False,
        controlled_demo_authorized=True,
    )
    assert sid
    assert svc.get_pending("ACC-1", "EURUSD") is None


def test_controlled_demo_cannot_carry_v53():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="GBPUSD",
        side="SELL",
        methodology="v53_6",
        production_authorized=False,
        controlled_demo_authorized=True,
    )
    assert sid
    assert svc.get_pending("ACC-1", "GBPUSD") is None


def test_production_authorized_still_works_for_non_research():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        methodology="baseline_demo",
        production_authorized=True,
        controlled_demo_authorized=False,
    )
    assert sid
    assert svc.get_pending("ACC-1", "EURUSD") is not None


def test_production_authorized_blocks_research_tokens():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        methodology="rsi9_transfer",
        production_authorized=True,
        controlled_demo_authorized=False,
    )
    assert sid
    assert svc.get_pending("ACC-1", "EURUSD") is None
