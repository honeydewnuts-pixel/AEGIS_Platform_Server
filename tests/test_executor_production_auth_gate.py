"""Executor queue: production_authorized must be explicit True."""
from app.services.executor_signal_service import ExecutorSignalService


def _pub(svc, **kw):
    defaults = dict(
        account_id="ACC1",
        symbol="EURUSD",
        side="SELL",
        confidence=1.0,
        rule_name="test",
        volume=0.01,
    )
    defaults.update(kw)
    return svc.publish(**defaults)


def test_production_authorized_returned():
    svc = ExecutorSignalService()
    sid = _pub(svc, production_authorized=True)
    assert sid
    row = svc.get_pending("ACC1", "EURUSD")
    assert row is not None
    assert row["signal_id"] == sid
    assert row.get("production_authorized") is True


def test_production_authorized_false_blocked():
    svc = ExecutorSignalService()
    _pub(svc, production_authorized=False)
    assert svc.get_pending("ACC1", "EURUSD") is None


def test_missing_authorization_blocked():
    svc = ExecutorSignalService()
    # default production_authorized=False
    _pub(svc)
    assert svc.get_pending("ACC1", "EURUSD") is None


def test_research_methodology_blocked_even_if_flag_true():
    svc = ExecutorSignalService()
    # Defense: research methodology tokens blocked even if flag wrongly True
    _pub(svc, production_authorized=True, methodology="rsi9_transfer")
    assert svc.get_pending("ACC1", "EURUSD") is None
    _pub(svc, production_authorized=True, methodology="native_discovery", symbol="GBPUSD")
    assert svc.get_pending("ACC1", "GBPUSD") is None


def test_good_tradeable_alone_insufficient():
    """Instrument authorization is separate; signal still needs production_authorized."""
    svc = ExecutorSignalService()
    _pub(svc, production_authorized=False, rule_name="good_tradeable_pair")
    assert svc.get_pending("ACC1", "EURUSD") is None
    assert ExecutorSignalService.is_execution_authorized(
        {"production_authorized": False, "methodology": ""}
    ) is False
    assert ExecutorSignalService.is_execution_authorized(
        {"production_authorized": True, "methodology": "v31_short_baseline"}
    ) is True
