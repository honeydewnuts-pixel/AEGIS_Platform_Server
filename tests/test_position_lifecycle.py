"""Position lifecycle + fail-closed authorization tests."""
from __future__ import annotations

from app.services.position_lifecycle_service import PositionLifecycleService


def _is_symbol_authorized_logic(reg, symbol: str):
    """Mirror executor_router fail-closed policy without importing FastAPI."""
    sym = (symbol or "").strip().upper().split(".")[0].split("#")[0]
    if not reg:
        return False, "registry_unavailable_fail_closed", None
    try:
        rows = reg.list_instruments(tradeable_only=False)
    except Exception:
        return False, "registry_error", None
    match = next((r for r in rows if str(r.get("instrument") or "").upper() == sym), None)
    if match is None:
        return False, "unknown_instrument", None
    if match.get("good") is False or not match.get("tradeable"):
        return False, f"not_authorized:{match.get('router_status')}", match
    return True, "ok", match


class _Reg:
    def list_instruments(self, tradeable_only=False):
        return [
            {"instrument": "EURUSD", "good": True, "tradeable": True, "router_status": "OK"},
            {"instrument": "NZDUSD", "good": False, "tradeable": False, "router_status": "RESEARCH"},
        ]


def test_registry_unavailable_fail_closed():
    ok, reason, _ = _is_symbol_authorized_logic(None, "EURUSD")
    assert ok is False
    assert "fail_closed" in reason


def test_unknown_instrument_rejected():
    ok, reason, _ = _is_symbol_authorized_logic(_Reg(), "FAKEPAIR")
    assert ok is False


def test_research_pair_rejected():
    ok, reason, _ = _is_symbol_authorized_logic(_Reg(), "NZDUSD")
    assert ok is False


def test_good_pair_allowed():
    ok, reason, _ = _is_symbol_authorized_logic(_Reg(), "EURUSD")
    assert ok is True


def test_ack_without_position_does_not_record_risk():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S1", ok=True, position_ticket=0,
        order_ticket=1, deal_ticket=0, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=10.0, idempotent=False,
    )
    assert life.should_record_open_risk("A1", "S1") is False
    assert life.get_signal_state("A1", "S1") == "ORDER_SENT"


def test_confirmed_open_records_risk_once():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S2", ok=True, position_ticket=999,
        order_ticket=1, deal_ticket=2, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=12.5, idempotent=False,
    )
    assert life.should_record_open_risk("A1", "S2") is True
    life.mark_open_risk_recorded("A1", "S2", 12.5)
    assert life.should_record_open_risk("A1", "S2") is False
    assert life.get_signal_state("A1", "S2") == "POSITION_OPEN"


def test_close_releases_once():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S3", ok=True, position_ticket=100,
        order_ticket=1, deal_ticket=2, symbol="EURUSD", side="BUY",
        volume=0.1, risk_usd=8.0, idempotent=False,
    )
    life.mark_open_risk_recorded("A1", "S3", 8.0)
    r1, s1 = life.on_broker_close(account_id="A1", signal_id="S3", position_ticket=100, symbol="EURUSD", risk_usd=None)
    assert r1 == 8.0 and s1 == "RISK_RELEASED"
    r2, s2 = life.on_broker_close(account_id="A1", signal_id="S3", position_ticket=100, symbol="EURUSD", risk_usd=None)
    assert r2 is None and s2 == "ALREADY_RELEASED"


def test_reconcile_clears_stale_and_sets_sides():
    life = PositionLifecycleService()
    life.on_ack(
        account_id="A1", signal_id="S4", ok=True, position_ticket=50,
        order_ticket=1, deal_ticket=1, symbol="EURUSD", side="SELL",
        volume=0.1, risk_usd=5.0, idempotent=False,
    )
    summary = life.reconcile_from_broker(
        "A1", [{"symbol": "GBPUSD", "side": "BUY", "position_ticket": 77}],
    )
    assert "GBPUSD" in summary["symbols"]
    assert life.broker_side("A1", "GBPUSD") == "BUY"
    assert summary["stale_tickets_cleared"] >= 1


def test_client_risk_ignored_without_server_record():
    life = PositionLifecycleService()
    r, s = life.on_broker_close(account_id="A1", signal_id="NONE", position_ticket=1, symbol="EURUSD", risk_usd=99.0)
    assert r is None
    assert s == "RECONCILIATION_REQUIRED"
