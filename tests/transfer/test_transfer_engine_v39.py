import numpy as np
import pandas as pd
from app.transfer.normalization import causal_features
from app.transfer.forex_transfer import ForexTransferEngine


def sample(n=300):
    x = np.arange(n, dtype=float) * 0.00001 + 1.1
    return pd.DataFrame(
        {
            "BidOpen": x,
            "BidHigh": x + 0.0002,
            "BidLow": x - 0.0002,
            "BidClose": x + 0.00005,
            "AskOpen": x + 0.00001,
            "AskHigh": x + 0.00021,
            "AskLow": x - 0.00019,
            "AskClose": x + 0.00006,
        }
    )


def test_normalization_is_causal():
    df = sample()
    a = causal_features(df)
    assert a.loc[100, "structural_range_12_atr"] == a.loc[100, "structural_range_12_atr"]
    changed = df.copy()
    changed.loc[101, "BidHigh"] += 0.5
    b = causal_features(changed)
    assert a.loc[100, "structural_range_12_atr"] == b.loc[100, "structural_range_12_atr"]


def test_unknown_source_fail_closed():
    e = ForexTransferEngine()
    r = e.eligibility(
        "BAD", "EURUSD", data_available=True, data_valid=True, spread_available=True, enough_history=True
    )
    assert r.status == "TRANSFER_NOT_ELIGIBLE"


def test_missing_data_fail_closed():
    e = ForexTransferEngine()
    r = e.eligibility(
        "AEGIS-RB-V31-GBPUSD-5M",
        "EURUSD",
        data_available=False,
        data_valid=False,
        spread_available=False,
        enough_history=False,
    )
    assert r.status == "DATA_NOT_AVAILABLE"
