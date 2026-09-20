from backend.app.services.executor_signal_service import ExecutorSignalService


def test_publish_get_ack():
    s = ExecutorSignalService(max_age_sec=60)
    sid = s.publish(account_id="ACC-1", symbol="GBPUSD", side="BUY", confidence=0.8, rule_name="test")
    assert sid
    row = s.get_pending("ACC-1", "GBPUSD")
    assert row is not None
    assert row["side"] == "BUY"
    assert s.ack("ACC-1", sid, ticket=123, ok=True)
    assert s.get_pending("ACC-1", "GBPUSD") is None


def test_hold_not_published():
    s = ExecutorSignalService()
    assert s.publish(account_id="ACC-1", symbol="GBPUSD", side="HOLD") is None
