"""Durable lifecycle logic tests (no DB required for pure service rules mirrored in memory service)."""
from __future__ import annotations

from app.services.position_lifecycle_service import PositionLifecycleService


def test_duplicate_close_no_second_release():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S1", ok=True, position_ticket=10,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=5.0, idempotent=False,
    )
    life.mark_open_risk_recorded("A1", "S1", 5.0)
    r1, s1 = life.on_broker_close(account_id="A1", signal_id="S1", position_ticket=10, symbol="EURUSD")
    r2, s2 = life.on_broker_close(account_id="A1", signal_id="S1", position_ticket=10, symbol="EURUSD")
    assert r1 == 5.0 and s1 == "RISK_RELEASED"
    assert r2 is None and s2 == "ALREADY_RELEASED"


def test_account_isolation_keys():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="SAME", ok=True, position_ticket=1,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="BUY",
        volume=0.1, risk_usd=3.0, idempotent=False,
    )
    life.mark_open_risk_recorded("A1", "SAME", 3.0)
    life.on_ack(
        account_id="A2", signal_id="SAME", ok=True, position_ticket=2,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="BUY",
        volume=0.1, risk_usd=7.0, idempotent=False,
    )
    life.mark_open_risk_recorded("A2", "SAME", 7.0)
    r1, _ = life.on_broker_close(account_id="A1", signal_id="SAME", position_ticket=1, symbol="EURUSD")
    r2, _ = life.on_broker_close(account_id="A2", signal_id="SAME", position_ticket=2, symbol="EURUSD")
    assert r1 == 3.0
    assert r2 == 7.0


def test_no_client_invented_risk_without_record():
    life = PositionLifecycleService()
    r, s = life.on_broker_close(
        account_id="A1", signal_id="X", position_ticket=99, symbol="EURUSD", risk_usd=100.0
    )
    assert r is None
    assert s == "RECONCILIATION_REQUIRED"


def test_ack_without_ticket_no_risk():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S2", ok=True, position_ticket=0,
        order_ticket=5, deal_ticket=0, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=4.0, idempotent=False,
    )
    assert life.should_record_open_risk("A1", "S2") is False


def test_duplicate_ack_no_second_risk_flag():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S3", ok=True, position_ticket=3,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="BUY",
        volume=0.1, risk_usd=2.0, idempotent=False,
    )
    assert life.should_record_open_risk("A1", "S3") is True
    life.mark_open_risk_recorded("A1", "S3", 2.0)
    assert life.should_record_open_risk("A1", "S3") is False
