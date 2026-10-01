# Native Discovery — Failed Transfer Instruments — 2026-10-01

Independent discovery (not RSI9-SHORT transfer) on instruments that failed transfer gates.

## Qualified (GOOD / RESEARCH_ELIGIBLE, production_authorized=false)

| Symbol | Class | Best rule | Side | Val n | Val PF | Val block | Test PF |
|--------|-------|-----------|------|------:|-------:|----------:|--------:|
| GER40 | INDEX | long_rsi9_lt30 | long | 2210 | 1.844 | 1.504 | 1.476 |
| UK100 | INDEX | long_z60_lt-1.5 | long | 2737 | 1.665 | 1.25 | 1.575 |
| UKOIL | COMMODITY | long_failed_breakout20 | long | 2040 | 1.738 | 1.508 | 1.59 |
| US100 | INDEX | long_rsi9_lt30 | long | 2175 | 1.638 | 1.323 | 1.391 |
| USDJPY | FOREX | long_ema_pullback | long | 2151 | 1.696 | 1.49 | 2.075 |
| XAGUSD | METAL | long_rsi9_lt25 | long | 1140 | 1.841 | 1.35 | 1.581 |

## Not qualified

| Symbol | Class | Best attempt | Val PF | Notes |
|--------|-------|--------------|-------:|-------|
| US500 | INDEX | long_bb20_lower | 1.588 | below gates |
| USOIL | COMMODITY | long_failed_breakout20 | 1.533 | below gates |
| XAUUSD | METAL | long_z60_lt-1.5 | 1.494 | below gates |

JSON: `registry/v40/rulebooks_native/`
