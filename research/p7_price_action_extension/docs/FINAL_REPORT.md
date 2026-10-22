# P7 Price-Action Extension — Final Report

**Branch:** `research/p7-price-action-extension-20261022`  
**Preregistration commit:** `96ab77d` (before outcomes)  
**production_authorized=false · execution_authorized=false**

## A. Executive conclusion

- Evaluated frozen hypotheses **P7-L1** and **P7-L2** on **Track A (H1 XAUUSD)** using exact feature formulas from `P7_Gold_Cash_Replay_Engine.py`.
- XAUUSD M5 SHA-256 **matches** P7 training input (`88e00425…`). Model file SHA-256 **matches** frozen model (`18380c1e…`).
- Original cash ledgers and full independent reproduction of in-sample cash PF: **not independently reproduced** (archives lack raw training CSVs used for GBPUSD condition; gold data available).
- **P7-L1** shows an exploratory positive forward association on the validation segment (mean price move > 0.42 RT cost at H1 horizons 1–8, hit rates ~0.61–0.71, n≥78 non-overlapping). Status: **EXPLORATORY_PROMISING_UNCONFIRMED**.
- **P7-L2** is weaker; short horizons fail materiality; longer horizons modest. Status: **EXPLORATORY_INCONCLUSIVE**.
- **No cash strategy PF** computed (no registered stop/target/sizing for this phase).
- **Independent confirmation unavailable** (final 20% EXPOSED; original study was in-sample).
- Next step: prospective confirmation design on new data — do not retune thresholds on exposed history.

## B. Provenance

| Claim | Classification |
|-------|----------------|
| Model SHA 18380c1e… | SOURCE_VERIFIED (file in archive + local copy) |
| Feature formulas | SOURCE_VERIFIED (engine source) |
| XAUUSD training hash 88e00425… | SOURCE_VERIFIED + matches local file |
| GBPUSD training hash fc9bf41… | UNVERIFIABLE_WITH_AVAILABLE_INPUTS (local Bid/Ask hash differs) |
| 528 / 1913 signal intents | SOURCE_REPORTED |
| Leaf values +0.05877R / +0.02786R | SOURCE_REPORTED (model values, not realized) |
| Forward associations this study | NEWLY_COMPUTED |
| Cash PF from archives | SOURCE_REPORTED only (in-sample) |

Archive zips from Google Drive `AEGIS_Pattern`:
- P7_Unchanged_Frozen.zip SHA256 `f2d22103…`
- TH025_Unchanged_Parent_P7.zip SHA256 `5841a133…`

## C. Features

Exact formulas (see `scripts/p7_features.py` and FEATURE_DICTIONARY in prereg). H1 aggregation requires complete 12×M5 bars with regular spacing.

## D. Hypotheses

Registered exactly as prereg (thresholds from long_tree). Short-side not registered (SOURCE_REPORTED max short leaf < 0.025R).

## E. Methodology

Prereg committed at `96ab77d` before outcome tables. Association layer only. Chronological 60/20/20; final 20% labelled EXPOSED.

## F. Results (Track A XAUUSD H1)

| Hypothesis | Total events | Val events | Val n (h=4, nonoverlap) | Val mean price | Val hit | Material vs 0.42 cost |
|------------|-------------:|-----------:|------------------------:|---------------:|--------:|:---------------------:|
| P7-L1 | 547 | 97 | 82 | +5.14 | 0.66 | Yes |
| P7-L2 | 1496 | 297 | 259 | +1.04 | 0.58 | Yes (weak) |

Dev h=4 nonoverlap: L1 mean_price +0.98; L2 +0.44.

## G. Economic interpretation

L1 residual mean price move on validation exceeds stated RT cost, but:
1. Original model was fit on this history (in-sample leakage of selection).
2. No executable stop/target tested.
3. OHLC path ambiguity for MAE/MFE sequence.
4. Not independent confirmation.

## H. Limitations

- GBPUSD condition file hash mismatch → FX filter in original prepare() not reproduced.
- Track B M5 analogue not registered.
- Class A FX transfer not run in this checkpoint (scope: primary Track A gold).
- No cash ledger newly computed.

## I. Decision register

| Hypothesis | Status |
|------------|--------|
| P7-L1 | EXPLORATORY_PROMISING_UNCONFIRMED |
| P7-L2 | EXPLORATORY_INCONCLUSIVE |
| Short-side | NOT_EVALUATED (reported negative leaf) |
| Track B M5 | NOT_EVALUATED |

## J. Next step

1. Do not expand or retune P7 thresholds on exposed data.
2. If pursuing L1: design prospective confirmation (new post-2026-09 data or paper period) with pre-registered entry (post decision_time Ask), stop/target, and cost model.
3. Optional: Class A FX structural occurrence scan without claiming gold transfer.

## Tests

`tests/test_p7_features.py` → **10 PASS / 0 FAIL**

## Authorization

Unchanged. No V53.6, no production merge, no live/demo orders.
