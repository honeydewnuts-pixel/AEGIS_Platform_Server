# AEGIS Visual Swing-Trend Rulebook V1.0 — Consolidated Report
**Date:** 2026-10-27  
**Branch:** `research/visual-swing-trend-v1-20261027`  
**production_authorized=false · execution_authorized=false**

## A. Repository / checkpoint
- Work performed on dedicated research branch from docs checkpoint lineage.
- Pre–Variant B-V reference (not main): `579180d` (historical ARRS Stage 1).
- Remote **main** remains separate platform HEAD (see prior reconciliation: `f546af7`).
- **No merge to main. No production/executor/EA/DB changes.**

## B. Dataset inventory
File: `research/visual_swing_trend_v1/data/dataset_inventory.csv` — **30** files.

| Class | Count | Notes |
|-------|------:|-------|
| FX Bid/Ask (Class A) | 13 | ~5Y M5, suitable for later Bid/Ask studies |
| FX/Alt OHLC (Class B) | 11 | ~5Y M5 |
| Volatility index (Drive) | 6 | **OHLC only**, shorter span |

### Volatility CSVs (Google Drive `Volatility_Index_More CSV`) — SOURCE-VERIFIED after download
| File | Rows | Range (UTC) | Class |
|------|-----:|-------------|-------|
| V75_M5_5Y.csv | 48000 | 2026-05-12 → 2026-10-26 | B_OHLC (~5.5 months, not 5Y despite name) |
| V75_1S_M5_5Y.csv | 18000 | 2026-08-24 → 2026-10-26 | B_OHLC |
| V100_M5_5Y.csv | 48000 | 2026-05-12 → 2026-10-26 | B_OHLC |
| V50_M5_5Y.csv | 18000 | 2026-08-24 → 2026-10-26 | B_OHLC |
| BOOM1000_M5_5Y.csv | 48000 | 2026-05-12 → 2026-10-26 | B_OHLC |
| CRASH1000_M5_5Y.csv | 18000 | 2026-08-24 → 2026-10-26 | B_OHLC |

**Limitation:** No Bid/Ask on volatility files → signal diagnostics only; not broker-realistic P&L.

## C. Rulebook
Human-readable formal text:  
`research/visual_swing_trend_v1/docs/RULEBOOK_V1.0_HUMAN.md`

Covers: indicators, trend context, causal swing proposal, INITIAL_SELL/BUY, ADD with one-per-pullback intent, reversal **blocked**, event model, out-of-scope items.

## D. Operator decisions required (do not freeze without answers)
See `OPERATOR_DECISION_REGISTER.md`:

1. **D1** OBB on RSI9 (O1) vs MA7 (O2)  
2. **D2** Accept 2-bar causal swing confirm?  
3. **D3** Multi-candle INITIAL completion OK?  
4. **D4** RSI swing type for SELL  
5. **D5** Exact “pullback toward BB34_U”  
6. **D6** “Substantially outside” → **A / B(k=?) / C** — **blocks reversal**  
7. **D7** Full BUY/SELL symmetry?

## E. Verification
```text
python3 research/visual_swing_trend_v1/tests/test_indicators_v1.py
→ TOTAL 7 PASS 0 FAIL
```
**TEST-VERIFIED** on this run. Covers BB order, RSI range, OBB presence, warm-up NaNs, swing non-lookahead on synthetic data.

## F. Research results (diagnostic only — not full Rulebook signals)
V75 → M15 resample (16001 bars, 2026-05-12 → 2026-10-26), OBB-on-RSI provisional:

| Metric | Count |
|--------|------:|
| BB17_U outside-above bars | 7627 |
| New BB17_U outside-above crosses | 310 |
| MA7 cross above OBB_M | 524 |
| MA7 cross above OBB_U | 35 |
| BB34_U exposed bars | 8341 |

**Full INITIAL/ADD/REVERSAL signal counts are NOT claimed** — blocked by open decisions D1–D7.

Screenshot (Drive `Bulider_Screenshot`) was inspected earlier; annotations are illustrative only.

## G. Reproducibility
- Indicators: `research/visual_swing_trend_v1/scripts/indicators_v1.py`
- Tests: `…/tests/test_indicators_v1.py`
- Inventory: `…/data/dataset_inventory.csv`
- V75 diagnostic: `…/outputs/v75_m15_diagnostic.csv`
- Vol CSVs path: `/home/workdir/artifacts/VOL_CSV/` (from Drive)

## H. Safety
**None** of: production changes, executor publish, EA install, broker orders, auth elevation, merge to main.

## I. Recommendation
1. Operator answers **D1–D7** (especially **D6** for reversal).  
2. Then freeze V1.0.1 specification and implement full event engine.  
3. Run M15 signal study per instrument **without** inventing exits or costs.  
4. Do **not** parameter-tune on V75 short sample to force attractiveness.  
5. Extend V75 history if true multi-year data becomes available.

**Status:** Specification + data inventory + indicator foundation **complete**. Full strategy evaluation **BLOCKED** on operator decisions. Reversal **BLOCKED**. Not profitable, not qualified, not authorized.
