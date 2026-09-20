# V2-OPT status (2026-09-20)

V2-OPT rulebooks are **archived** and **not** used for demo/live routing.

## Why
Original gates: val_n>=40, PF>=1.15, val halves — NOT val_n>300 / PF>1.6 / 6-block min>1.

## Effect
- Multi-book pairs: V2-OPT stripped from eligible_rulebooks.
- V2-OPT-only (EURUSD, USDJPY, EURJPY, GBPAUD): TRADING_DISABLED, Not Good.
- All AEGIS-RB-V2OPT-*: RESEARCH_ARCHIVED_INSUFFICIENT_GATES.
