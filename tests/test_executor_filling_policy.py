"""Document expected MQL5 filling policy selection (mirror of EA ResolveOrderFilling)."""


def resolve_fill(exec_mode: str, filling_flags: int) -> list[str]:
    """Mirror GetSupportedFillModes without MQL5.

    filling_flags: bit0 FOK=1, bit1 IOC=2 (MetaQuotes SYMBOL_FILLING_*).
    """
    allow_fok = bool(filling_flags & 1)
    allow_ioc = bool(filling_flags & 2)
    modes: list[str] = []
    market = exec_mode in ("MARKET", "EXCHANGE")
    instant = exec_mode in ("INSTANT", "REQUEST")
    if market:
        if allow_ioc:
            modes.append("IOC")
        if allow_fok:
            modes.append("FOK")
        if not modes and filling_flags == 0:
            modes.extend(["IOC", "FOK"])
    elif instant:
        if allow_ioc:
            modes.append("IOC")
        if allow_fok:
            modes.append("FOK")
        if not modes or filling_flags == 0:
            modes.append("RETURN")
    else:
        if allow_ioc:
            modes.append("IOC")
        if allow_fok:
            modes.append("FOK")
    return modes


def test_market_never_returns_return():
    for flags in (0, 1, 2, 3):
        modes = resolve_fill("MARKET", flags)
        assert "RETURN" not in modes
        assert modes  # never empty for market with 0 or flags


def test_exchange_same_as_market():
    assert "RETURN" not in resolve_fill("EXCHANGE", 3)


def test_instant_allows_return_when_no_flags():
    modes = resolve_fill("INSTANT", 0)
    assert "RETURN" in modes


def test_market_ioc_fok_flags():
    assert resolve_fill("MARKET", 2) == ["IOC"]
    assert resolve_fill("MARKET", 1) == ["FOK"]
    assert resolve_fill("MARKET", 3) == ["IOC", "FOK"]


def test_unknown_exec_no_return():
    assert "RETURN" not in resolve_fill("OTHER", 0)
    assert resolve_fill("OTHER", 0) == []
