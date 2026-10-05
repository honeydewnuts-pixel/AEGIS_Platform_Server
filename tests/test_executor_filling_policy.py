"""Mirror of EA GetSupportedFillModes — fail-closed Market/Exchange."""


def resolve_fill(exec_mode: str, filling_flags: int) -> list[str]:
    """filling_flags: FOK=1, IOC=2 (MetaQuotes SYMBOL_FILLING_*)."""
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
        # fail closed: no invented modes when flags==0
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


def test_market_flags_0_empty():
    assert resolve_fill("MARKET", 0) == []


def test_exchange_flags_0_empty():
    assert resolve_fill("EXCHANGE", 0) == []


def test_market_ioc():
    assert resolve_fill("MARKET", 2) == ["IOC"]


def test_market_fok():
    assert resolve_fill("MARKET", 1) == ["FOK"]


def test_market_ioc_fok():
    assert resolve_fill("MARKET", 3) == ["IOC", "FOK"]


def test_market_exchange_never_return():
    for flags in (0, 1, 2, 3):
        assert "RETURN" not in resolve_fill("MARKET", flags)
        assert "RETURN" not in resolve_fill("EXCHANGE", flags)


def test_instant_may_return():
    assert "RETURN" in resolve_fill("INSTANT", 0)
    assert "RETURN" in resolve_fill("REQUEST", 0)


def test_unknown_no_flags_empty():
    assert resolve_fill("OTHER", 0) == []
