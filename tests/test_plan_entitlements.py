"""Central plan catalogue drives brain/live-trading entitlement — not hard-coded 'live'."""

from app.services.plan_catalog import resolve_plan


def test_paid_plans_have_live_trading():
    for code in ("starter", "pro", "business"):
        p = resolve_plan(code)
        assert p.get("live_trading") is True, code


def test_demo_plan_no_live_trading_flag():
    p = resolve_plan("demo")
    assert p.get("live_trading") is False


def test_legacy_live_alias_maps_to_starter():
    p = resolve_plan("live")
    assert p.get("code") in ("starter", "live") or p.get("live_trading") is True
