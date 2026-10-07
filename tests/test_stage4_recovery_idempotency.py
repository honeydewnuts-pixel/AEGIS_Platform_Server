"""Stage 4 — recovery, idempotency, governance (no strategy promotion)."""
from __future__ import annotations

from app.services.executor_signal_service import ExecutorSignalService


def test_duplicate_ack_is_idempotent():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-S4",
        symbol="EURUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        volume=0.01,
        risk_usd_at_open=10.0,
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    assert sid
    r1 = svc.ack("ACC-S4", sid, ticket=101, position_ticket=101, ok=True, symbol="EURUSD", side="SELL", volume=0.01)
    assert r1.get("acked") is True
    assert r1.get("idempotent") is not True  # first ACK
    r2 = svc.ack("ACC-S4", sid, ticket=101, position_ticket=101, ok=True, symbol="EURUSD", side="SELL", volume=0.01)
    assert r2.get("acked") is True
    assert r2.get("idempotent") is True
    r3 = svc.ack("ACC-S4", sid, ticket=101, position_ticket=101, ok=True)
    assert r3.get("idempotent") is True
    # Pending cleared; no second logical order
    assert svc.get_pending("ACC-S4", "EURUSD") is None


def test_signal_id_stable_single_pending_per_symbol():
    svc = ExecutorSignalService()
    s1 = svc.publish(
        account_id="ACC-S4",
        symbol="GBPUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    s2 = svc.publish(
        account_id="ACC-S4",
        symbol="GBPUSD",
        side="SELL",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    # Latest pending wins for symbol key; both IDs distinct; only one pending row
    assert s1 != s2
    row = svc.get_pending("ACC-S4", "GBPUSD")
    assert row is not None
    assert row["signal_id"] == s2


def test_ack_failure_then_success_path():
    svc = ExecutorSignalService()
    sid = svc.publish(
        account_id="ACC-S4",
        symbol="EURUSD",
        side="BUY",
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        controlled_demo_authorized=True,
        production_authorized=False,
    )
    fail = svc.ack("ACC-S4", sid, ok=False, retcode=10016, message="reject")
    assert fail.get("acked") is True
    # Completed — further ACK idempotent
    again = svc.ack("ACC-S4", sid, ok=True, position_ticket=99)
    assert again.get("idempotent") is True


def test_recovery_cannot_promote_research_or_production():
    svc = ExecutorSignalService()
    for meth in ("v53_6", "rsi9_transfer", "native_discovery", "generation3_x"):
        svc.publish(
            account_id="ACC-S4",
            symbol="EURUSD",
            side="SELL",
            methodology=meth,
            production_authorized=True,
            controlled_demo_authorized=True,
        )
        assert svc.get_pending("ACC-S4", "EURUSD") is None, meth


def test_settings_production_authorized_false():
    from app.config import settings
    assert bool(getattr(settings, "PRODUCTION_AUTHORIZED", False)) is False


def test_executor_source_has_restart_reconcile_hooks():
    from pathlib import Path
    src = Path("release/desktop/AEGIS_Executor.mq5").read_text()
    assert "ReconcileBrokerPositionsOnStartup" in src or "reconcile-positions" in src
    assert "DetectDisappearedPositions" in src
    assert "WasHandled" in src or "MarkHandled" in src
