# Data-Driven Pattern Discovery Programme — Final Report

**Branch:** `research/data-driven-pattern-discovery-20261022`  
**Base:** `64bc989` (V7/all-instrument checkpoint lineage)  
**production_authorized=false · execution_authorized=false**

## 1. Datasets

All **24** five-year M5 datasets verified and processed (13 Class A Bid/Ask, 11 Class B OHLC).  
Inventory: `outputs/dataset_inventory.csv` with SHA-256.

## 2. Methods actually run

1. Registered binary pattern enumeration (22 patterns: candle geometry, range structure, session hours, breakouts, interactions)
2. Conditional forward-return analysis at horizons 3, 6, 12, 24, 48 M5 bars
3. Chronological 60/20/20 splits per instrument
4. Support filter (dev n ≥ 200), same-sign(dev,val), val_n ≥ 50 for survivor list

**Not run** (documented limits): unrestricted clustering, deep trees, sparse regression search, leave-one-instrument-out transfer battery.

## 3. Search space

- 22 patterns × 5 horizons × 24 instruments = **2,640** pattern–horizon–instrument evaluations  
- Multiple-testing risk is material; no naive p-values treated as confirmation

## 4. Results

| Stage | Count |
|-------|------:|
| Total evaluations | 2,640 |
| With development support ≥200 | large majority of registered patterns |
| Same-sign(dev,val) + support + val_n≥50 | **1,837** |
| |mean_val| > 10 bps AND hit>0.55 AND val_n>200 | **≈0–few** (see materiality note) |

Top absolute mean validation returns are on the order of **5–9 bps over 48 bars** (crypto/metals), with hit rates ~0.52–0.57. For forex Class A, effects are smaller relative to typical spread + commission.

## 5. Interpretation

- **Patterns exist** in the weak statistical sense (same-sign conditional means with support).
- **Effect sizes are small** relative to realistic transaction costs on Class A data.
- **No candidate was converted into a complete trading rulebook** in this checkpoint.
- **No candidate passed V7 three-gate strategy qualification** (not applied; no cash model built).
- Historical final 20% remains **EXPOSED** from prior AEGIS work.

## 6. Cross-instrument

Same pattern names appear across many instruments, but magnitudes differ. No transfer confirmation protocol was completed that freezes discovery instruments vs holdout instruments under a locked shortlist.

## 7. Leakage tests

`tests/test_features_leakage.py` → **5 PASS / 0 FAIL** (prefix invariance, label end-NaN, past-only range window).

## 8. Strongest next research step

1. Materiality filter: require conditional mean move ≫ instrument median spread before strategy construction.  
2. Freeze a tiny shortlist of structurally distinct patterns (e.g. range expansion after compression; break of 20-bar low with lower-wick rejection) and evaluate cost-aware excursions (MFE/MAE) with Bid/Ask fills on Class A only.  
3. Do not expand the pattern catalogue blindly.

## 9. Qualification matrix

**0 rulebooks qualified.** Programme completed as pattern-level evidence survey with explicit negative strategy conclusion under cost realism.
