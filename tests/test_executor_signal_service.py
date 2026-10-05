from backend.app.services.executor_signal_service import ExecutorSignalService


def test_publish_get_ack_idempotent():
    s = ExecutorSignalService(max_age_sec=60)
    sid = s.publish(
        account_id="ACC-1",
        symbol="GBPUSD",
        side="BUY",
        confidence=0.8,
        production_authorized=True,
    )
    assert sid
    assert s.get_pending("ACC-1", "GBPUSD")["side"] == "BUY"
    r1 = s.ack("ACC-1", sid, order_ticket=10, deal_ticket=20, position_ticket=30, ok=True)
    assert r1["acked"] is True
    assert s.get_pending("ACC-1", "GBPUSD") is None
    r2 = s.ack("ACC-1", sid, order_ticket=10, ok=True)
    assert r2["acked"] is True and r2.get("idempotent") is True


def test_multi_pair_independent():
    s = ExecutorSignalService()
    s.publish(account_id="ACC-1", symbol="GBPUSD", side="BUY", production_authorized=True)
    s.publish(account_id="ACC-1", symbol="EURUSD", side="SELL", production_authorized=True)
    rows = s.get_pending_many("ACC-1", ["GBPUSD", "EURUSD", "USDJPY"])
    sides = {r["symbol"]: r["side"] for r in rows}
    assert sides["GBPUSD"] == "BUY"
    assert sides["EURUSD"] == "SELL"


def test_unauthorized_publish_not_returned():
    s = ExecutorSignalService()
    s.publish(account_id="ACC-1", symbol="GBPUSD", side="BUY", production_authorized=False)
    assert s.get_pending("ACC-1", "GBPUSD") is None
