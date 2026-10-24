# Variant B-V Source Audit

## Reference artifacts
- M5_VariantB_V.zip / M15_VariantB_V.zip (Drive Variant_B folder)
- Source_Codes.zip → variant_bv_source.py (primary)
- Variant_B.zip was **0 bytes** (empty download)

## Defects identified

| ID | Issue | Classification |
|----|-------|----------------|
| D1 | Signal at bar t uses close; entry at `d.open.iloc[t]` | **Corrected** → next-bar executable price |
| D2 | `downtrend = (b17u < b34l) & (b17u < b34l)` repeated tautology | **Corrected** → mirror of uptrend: `(b17u < b34u) & (b17l < b34l)` as versioned CORRECTED_DOWNTREND; legacy preserved as LEGACY |
| D3 | Time stop 576 bars (48h only on continuous M5) | **Corrected** → elapsed timestamp ≥ 48 hours |
| D4 | ATR = rolling mean TR (not Wilder) | **Verified original** — preserved in baseline |
| D5 | Variables named ema17/34 are SMA | **Verified original** — preserved |
| D6 | Equity series = cash only (no MTM) | **Corrected** — report cash and MTM separately |
| D7 | Fixed cost 0.00019 | **GBPUSD-labelled reference cost** (1.9 pip); not transferred blindly |
| D8 | resample requires volume column | **Corrected** — optional volume |
| D9 | End-of-data open positions | **Corrected** — explicit FORCE_CLOSE_EOD or leave OPEN_FLAGGED |
| D10 | Same-bar reverse exit at open after close-based signal | **Corrected** with next-bar convention |

## Intended downtrend
Rulebook: "block longs in confirmed BB17/BB34 downtrend; block shorts in confirmed uptrend."
Uptrend in source: `(b17u > b34u) & (b17l > b34l)`.
Symmetric correction for downtrend is the natural reconstruction; original expression is a bug.

## Status
production_authorized=false · execution_authorized=false
