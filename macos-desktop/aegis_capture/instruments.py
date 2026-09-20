"""AEGIS instrument catalog for pair/symbol dropdown (Win/Mac)."""

# Good: non-V2OPT rulebooks (V31/V35/V53.6). Research-eligible on server.
GOOD: list[str] = [
    "GBPUSD",
    "AUDUSD",
    "USDCHF",
    "NZDUSD",
    "EURCHF",
    "EURGBP",
    "GBPJPY",
    "GBPNZD",
    "NZDCHF",
    "NZDJPY",
    "USDCAD",
]

# V2-OPT only — TRADING_DISABLED on server (insufficient gates).
NOT_GOOD: list[str] = [
    "EURUSD",
    "USDJPY",
    "EURJPY",
    "GBPAUD",
]

AEGIS_INSTRUMENTS: list[str] = GOOD + NOT_GOOD

AEGIS_INSTRUMENT_LABELS: list[str] = [f"{s}  · Good" for s in GOOD] + [
    f"{s}  · Not Good (V2-OPT only)" for s in NOT_GOOD
]


def index_of(symbol: str | None) -> int:
    if not symbol:
        return 0
    u = symbol.strip().upper()
    try:
        return AEGIS_INSTRUMENTS.index(u)
    except ValueError:
        return 0


def symbol_from_label(label: str) -> str:
    return label.split("·")[0].strip().upper()


def is_good(symbol: str | None) -> bool:
    if not symbol:
        return False
    return symbol.strip().upper() in GOOD
