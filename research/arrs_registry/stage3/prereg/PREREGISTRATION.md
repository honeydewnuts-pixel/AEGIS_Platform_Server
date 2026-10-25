# ARRS Stage 3 Preregistration
Commit-bound before performance evaluation.
production_authorized=false · execution_authorized=false

## Policy
- Evaluator: ARRS_STAGE2_V1 (src/stage2)
- Partition: train 60% / val 20% / test 20% chronological
- Embargo: 0 bars (document limitation for overlapping holds)
- TM template (shared, frozen): TM_ATR_STOP_V1
  - initial_stop_atr: 1.5
  - max_hold_bars: 48
  - take_profit_atr: None
  - trail: None
  - same_bar_policy: stop_first
  - gap_policy: worse_open
- Costs: commission_per_side=0, slippage=0 (spread via Bid/Ask sides only)
- Account-currency sizing: NOT USED (price-unit PnL)
- Gates: GatePolicy ARRS_STAGE2_GATES_V1 defaults
- Class A Bid/Ask only for qualification
- Multiple testing: 2 candidates × N instruments; report unadjusted; block "qualified Rulebook" claim if any multi-instrument selection after seeing results

## Candidate A — CAND-S3-INSIDE-BREAK-V1
Hypothesis: After an inside bar, a close beyond the parent bar's high/low continues in that direction over the next holding window under ATR stop.
Signal (completed bar t):
- Bar t-1 is inside bar t-2 (high_t-1 <= high_t-2 and low_t-1 >= low_t-2)
- Long if close_t > high_t-2
- Short if close_t < low_t-2
Entry: next bar open (Ask long / Bid short)
Eligible: Class A M5 FX from inventory

## Candidate B — CAND-S3-RANGE20-BREAK-V1
Hypothesis: Close beyond prior 20-bar high/low initiates a short continuation move under ATR stop.
Signal at t:
- Long if close_t > max(high_{t-20:t-1})
- Short if close_t < min(low_{t-20:t-1})
Entry: next bar open Bid/Ask convention
Eligible: Class A M5 FX

## Explicit non-selections
- Variant B-V: excluded by Stage 3 directive
- P7-L1/L2: association-only historically; no frozen original TM — not selected to avoid retroactive TM assignment
- Pattern-discovery aggregate wave: already REJECTED at materiality gate

## Selection rationale
Two simple, fully specified price-structure rules drawn from the discovery programme's feature family, with complete causal definitions and one shared frozen TM, to test whether any minimal structure survives Stage 2 gates under Bid/Ask execution.
