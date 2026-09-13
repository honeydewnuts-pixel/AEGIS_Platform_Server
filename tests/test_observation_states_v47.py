from app.services.observation_package import (
    derive_acquisition_state,
    WAITING_FOR_OHLC,
    CAPTURE_COMPLETE,
    INSTRUMENT_BLOCKED,
)


def test_waiting_for_ohlc():
    acq = derive_acquisition_state(
        obs_flags={
            "screenshot_valid": True,
            "instrument_valid": True,
            "ohlc_valid": False,
            "timestamp_aligned": True,
        },
        router_state="ROUTABLE_RESEARCH",
        rule_name="v40_research_awaiting_ohlc",
    )
    assert acq["acquisition_state"] == WAITING_FOR_OHLC


def test_capture_complete():
    acq = derive_acquisition_state(
        obs_flags={
            "screenshot_valid": True,
            "instrument_valid": True,
            "ohlc_valid": True,
            "timestamp_aligned": True,
        },
        router_state="ROUTABLE_RESEARCH",
        rule_name="v40_research_ohlc_hold",
    )
    assert acq["acquisition_state"] == CAPTURE_COMPLETE


def test_instrument_blocked():
    acq = derive_acquisition_state(
        obs_flags={
            "screenshot_valid": True,
            "instrument_valid": True,
            "ohlc_valid": False,
            "timestamp_aligned": True,
        },
        router_state="TRADING_DISABLED",
        rule_name="trading_disabled",
    )
    assert acq["acquisition_state"] == INSTRUMENT_BLOCKED
