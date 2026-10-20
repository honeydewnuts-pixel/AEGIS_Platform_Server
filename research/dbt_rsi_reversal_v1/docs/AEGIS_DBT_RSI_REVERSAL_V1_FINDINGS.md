# AEGIS_DBT_RSI_REVERSAL_V1 — Research Findings (Signal/Event Stage)

**Branch:** `research/dbt-rsi-reversal-v1-20261020`  
**production_authorized:** false  
**execution_authorized:** false  

## What was implemented

- Indicator stack: BB34/BB17 on Close; RSI9; RSI_MA7 on RSI9; RBB(34,1.618) on RSI9; WPR60  
- Main-chart state engine (up/down established, retracement, deep retracement, neutral)  
- **PROVISIONAL** RSI swing L=2 R=2 (operator-final parameters not provided)  
- Early RSI reversal independent of main-chart weakening  
- Long and short  
- MA7/WPR60 recorded, not mandatory for eligibility  

## Signal counts (13 Bid/Ask M5 pairs, ~5Y)

| Metric | Value |
|--------|------:|
| Eligible early RSI reversals | **183,016** |
| Early bearish | 98,165 |
| Early bullish | 84,851 |

Per-instrument detail: `outputs/instrument_signal_summary.csv`  
Event ledger (eligible only): `outputs/early_rsi_event_ledger.csv`

## WPR60 vs RBB_U

Observed rate of `WPR60 > RBB_U` ≈ **0** across pairs. Expected: WPR ∈ [-100,0], RSI bands ∈ ~[0,100]. Cross-scale comparison is mathematically rare; reported as diagnostic, not a bug.

## Blocked / unresolved

1. **Operator-final RSI swing parameters** — provisional L=2,R=2 used  
2. **Structural reversal higher-high sequence** — not fully specified; engine not claimed complete  
3. **Trade management (stop/TP/trail/size)** — no net-profitability ledger  

## What this is NOT

- Not a profitability claim  
- Not a qualified Rulebook  
- Not production-authorized  

## Tests

```
python3 research/dbt_rsi_reversal_v1/tests/test_dbt_indicators.py
→ 14 PASS, 0 FAIL
```
