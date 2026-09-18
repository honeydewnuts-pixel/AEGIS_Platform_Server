"""AEGIS instrument catalog for pair/symbol dropdown (Win/Mac capture clients)."""

# ~24 instruments from discovery + V40/V53.6/V2-OPT registries
AEGIS_INSTRUMENTS: list[str] = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "EURCHF",
    "GBPJPY",
    "GBPAUD",
    "GBPNZD",
    "AUDJPY",
    "NZDJPY",
    "NZDCHF",
    "XAUUSD",
    "XAGUSD",
    "NAS100",
    "US500",
    "INDEX_MID2K",
    "BRENT",
    "BTCUSD",
    "VOL100",
]


def index_of(symbol: str | None) -> int:
    if not symbol:
        return 0
    u = symbol.strip().upper()
    try:
        return AEGIS_INSTRUMENTS.index(u)
    except ValueError:
        return 0
