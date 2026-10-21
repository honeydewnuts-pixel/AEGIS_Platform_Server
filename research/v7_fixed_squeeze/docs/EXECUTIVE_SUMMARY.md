# V7 Fixed Squeeze — All-Instrument Research Executive Summary

**Branch:** `research/v7-fixed-squeeze-all-instruments-20261021`  
**production_authorized:** false · **execution_authorized:** false

## Critical finding: baseline artifacts missing

The original V7 Fixed Squeeze implementation, GBPUSD/XAUUSD research report, and exact cost assumptions were **not found** in the AEGIS repository clone or artifact zips. The engine was **reconstructed from the frozen rule text in the research task** (BB20/2, squeeze pct, ATR expansion, breakout/pullback lookbacks, EMA stack, session 07–20 UTC).

**Baseline numerical reproduction of any prior published GBPUSD/XAUUSD performance is BLOCKED** until those artifacts are recovered.

## Dataset inventory

24 eligible five-year M5 CSVs discovered:

| Class | Count | Instruments |
|-------|------:|-------------|
| A Bid/Ask | 13 | AUDUSD, EUR*, GBP*, NZD*, USD* forex majors/crosses |
| B OHLC-only | 11 | NZDUSD, BTCUSD, ETHUSD, GER40, UK100, UKOIL, US100, US500, USOIL, XAGUSD, XAUUSD |

## Qualification result

**Zero candidates passed all three gates on any instrument.**

| Gate | Threshold | Outcome across study |
|------|-----------|----------------------|
| 1 Validation trades | > 350 | **Universal fail** — max observed **123** (BTCUSD B2_bo7) |
| 2 Validation net PF | > 1.6 | Occasional pass on Class B indices (UK100, US500, US100) only |
| 3 Six-block min PF | > 1.0 | Fail when trade counts are thin |

Controlled variants (A1 squeeze 0.45, B2 breakout 7, C2 pullback 5, D1 ATR 1.05) increased trade counts modestly but **nowhere near 350** validation trades.

## Rejection funnel (typical forex, baseline)

Session restriction and squeeze filter dominate rejections; then vol expansion and breakout; trend alignment is a smaller residual gate.

## Interpretation

Under the reconstructed rules and cost proxies used here, **opportunity frequency is the binding constraint**, not merely cost. Relaxing single-family parameters within the predeclared set does not produce Gate-1-eligible samples.

Class B index results with PF > 1.6 are **OHLC proxy only** — not verified Bid/Ask execution.

## Next step (not this task)

1. Recover original V7 source + GBPUSD/XAUUSD report for true baseline reconciliation.  
2. If frequency remains the bottleneck, a **new hypothesis** (not gate relaxation) is required.  
3. Do not promote any candidate.
