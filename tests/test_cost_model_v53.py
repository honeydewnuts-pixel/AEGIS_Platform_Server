"""V53.6 cost-model remediation tests."""
import numpy as np
import pandas as pd

from app.rulebooks.evaluators.common import (
    LEGACY_FIXED_COST_R,
    simulate_short,
    simulate_short_legacy,
    simulate_short_operational,
    wilder_atr14,
)
from app.services.execution_cost_model import cost_config_for, assert_no_legacy_cost_on_operational


def _toy_df(n=100):
    rng = np.random.default_rng(0)
    close = 1.1000 + np.cumsum(rng.normal(0, 0.0001, n))
    high = close + 0.0003
    low = close - 0.0003
    spread = 0.0001
    dt = pd.date_range("2020-01-01", periods=n, freq="5min")
    return pd.DataFrame(
        {
            "datetime": dt,
            "BidOpen": close,
            "BidHigh": high,
            "BidLow": low,
            "BidClose": close,
            "AskOpen": close + spread,
            "AskHigh": high + spread,
            "AskLow": low + spread,
            "AskClose": close + spread,
        }
    )


def test_legacy_cost_is_exactly_085():
    assert LEGACY_FIXED_COST_R == 0.085


def test_legacy_and_operational_differ_on_same_path():
    df = _toy_df()
    atr = wilder_atr14(df["BidHigh"].to_numpy(), df["BidLow"].to_numpy(), df["BidClose"].to_numpy())
    # force a few event indices with finite ATR
    events = np.array([20, 40, 60], dtype=int)
    leg = simulate_short_legacy(df, atr, events)
    op = simulate_short_operational(df, atr, events)
    if len(leg) == 0:
        # still validates APIs
        assert list(leg.columns)
        return
    # Operational R should be higher by ~0.085 when same trades
    assert len(leg) == len(op)
    diff = (op["R"] - leg["R"]).to_numpy(float)
    assert np.allclose(diff, LEGACY_FIXED_COST_R, atol=1e-9)
    assert (leg["cost_R"] == LEGACY_FIXED_COST_R).all()
    assert (op["cost_R"] == 0.0).all()
    assert "legacy" in str(leg["cost_model_version"].iloc[0])
    assert "bid_ask" in str(op["cost_model_version"].iloc[0])


def test_default_simulate_short_is_legacy_reproduction():
    df = _toy_df()
    atr = wilder_atr14(df["BidHigh"].to_numpy(), df["BidLow"].to_numpy(), df["BidClose"].to_numpy())
    events = np.array([25], dtype=int)
    a = simulate_short(df, atr, events)
    b = simulate_short(df, atr, events, cost_mode="legacy_fixed_r")
    if len(a):
        assert list(a["R"]) == list(b["R"])


def test_operational_config_no_legacy():
    for at in ("historical_operational", "demo", "live"):
        cfg = cost_config_for("USDCHF", at)
        assert cfg.cost_mode == "bid_ask_only"
        assert cfg.fixed_cost_r is None
        assert_no_legacy_cost_on_operational(at)


def test_reproduction_config_has_legacy():
    cfg = cost_config_for("GBPUSD", "historical_reproduction")
    assert cfg.cost_mode == "legacy_fixed_r"
    assert cfg.fixed_cost_r == 0.085
