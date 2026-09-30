"""Demo Execution Monitor — stage aggregation and event log."""
from __future__ import annotations

from app.services.trade_event_log import TradeEventLog
from app.services.demo_execution_monitor import DemoExecutionMonitor
from app.services.executor_signal_service import ExecutorSignalService
from app.services.ohlc_stream_service import OhlcStreamService


def test_trade_event_log_by_signal():
    log = TradeEventLog()
    log.record(stage="queued", account_id="ACC-1", status="QUEUED", signal_id="s1", symbol="GBPUSD")
    log.record(stage="ack", account_id="ACC-1", status="ACK_OK", signal_id="s1", symbol="GBPUSD")
    ev = log.for_signal("s1")
    assert len(ev) == 2
    assert log.for_account("ACC-1", limit=10)


def test_monitor_no_ohlc_disconnected():
    mon = DemoExecutionMonitor(TradeEventLog())
    out = mon.build(account_id="ACC-1", ohlc_stream=OhlcStreamService(), executor_signals=ExecutorSignalService())
    assert out["overall"]["code"] == "MT5_DISCONNECTED"
    statuses = {s["stage"]: s["status"] for s in out["stages"]}
    assert statuses["mt5_connection"] == "DISCONNECTED"


def test_monitor_signal_pending_executor_silent():
    ohlc = OhlcStreamService()
    ohlc.ingest(
        account_id="ACC-1",
        symbol="GBPUSD",
        timeframe="M5",
        bars=[{"time": 1, "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "tick_volume": 1}],
    )
    svc = ExecutorSignalService()
    sid = svc.publish(account_id="ACC-1", symbol="GBPUSD", side="SELL", confidence=0.8, volume=0.01)
    assert sid
    mon = DemoExecutionMonitor(TradeEventLog())
    out = mon.build(account_id="ACC-1", ohlc_stream=ohlc, executor_signals=svc)
    assert out["overall"]["code"] in ("SIGNAL_AWAITING_EXECUTION", "EXECUTOR_NOT_POLLING", "NO_SIGNAL")
    # pending should be visible
    assert any(s["status"] in ("SIGNAL_PENDING", "QUEUED") for s in out["stages"])


def test_publish_emits_queue_event_when_log_attached():
    log = TradeEventLog()
    svc = ExecutorSignalService()
    svc.event_log = log
    sid = svc.publish(account_id="ACC-2", symbol="USDCHF", side="SELL", confidence=0.9)
    assert sid
    events = log.for_signal(sid)
    assert events and events[0]["stage"] == "queued"


def test_ack_records_failure_in_recent():
    svc = ExecutorSignalService()
    sid = svc.publish(account_id="ACC-3", symbol="EURUSD", side="BUY", confidence=0.7)
    res = svc.ack("ACC-3", sid, ok=False, retcode=10016, message="invalid stops")
    assert res["acked"]
    recent = svc.recent_for_account("ACC-3")
    assert recent and recent[0]["ok"] is False
