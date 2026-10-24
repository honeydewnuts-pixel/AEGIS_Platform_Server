# Variant B-V — Acceptance Report
**Branch:** research/variant-bv-20261024  
**production_authorized=false · execution_authorized=false**

## Executive conclusion

1. **Source archives recovered** from Google Drive `Variant_B` folder (`M5_VariantB_V.zip`, `M15_VariantB_V.zip`, `Source_Codes.zip`). `Variant_B.zip` was empty (0 bytes).
2. **Material implementation defects** confirmed (look-ahead entry, broken downtrend filter, bar-count time stop, cash-only equity).
3. **Corrected causal engine (CAUSAL_V1)** implemented with next-bar Bid/Ask conventions, corrected downtrend symmetry, wall-clock 48h time stop.
4. **Reference GBPUSD results are NOT reproduced** by the causal engine — as expected when removing look-ahead fills.
5. Under causal execution, **GBPUSD and all tested Class A FX pairs show PF < 1 and severe capital loss**. Frozen corrected baseline **does not transfer** as a profitable Rulebook.
6. **No candidate is qualified** for demo or production. Controlled indicator discovery (Phase 8) was **not** used to retune into profitability; baseline failure is preserved.

## Reference (SOURCE_REPORTED, not independently reproduced as causal)

| TF | Trades | PF | Win% | Net | Max DD |
|----|-------:|---:|-----:|----:|-------:|
| M15 | 233 | 1.99 | 53.2 | +11014 | −5.81% |
| M5 | 685 | 1.40 | 44.8 | +20813 | −14.65% |

These used the original look-ahead open-at-signal-bar convention per `variant_bv_source.py`.

## Causal GBPUSD (NEWLY_COMPUTED)

| TF | Trades | PF | Win% | Net |
|----|-------:|---:|-----:|----:|
| M5 | 2291 | 0.59 | 26.0 | ≈ −9998 |
| M15 | 773 | 0.73 | 31.0 | ≈ −7209 |

## Transfer (partial Class A sample, CAUSAL_V1)

All completed rows in `outputs/transfer_results.csv` show PF < 1 on M5. Pattern consistent with no durable edge after causal fills + costs.

## Audit defects (summary)

See `docs/SOURCE_AUDIT.md`. Key: D1 look-ahead, D2 downtrend tautology, D3 576-bar time stop, D6 cash equity.

## Gates (V7-style research)

| Gate | Causal baseline |
|------|-----------------|
| Validation trades > 350 | M5 count high but not a pass given PF |
| Net PF > 1.6 | **FAIL** |
| Six-block min PF > 1.0 | **Not claimed** (losing overall) |
| Production authorization | **false** |

## Classification

**Non-transfer / fails materiality under causal execution.**

## Limitations

- Full 24×2 matrix may be incomplete if background job interrupted; existing rows already show systematic failure.
- Cost model for non-GBPUSD is placeholder pip assumptions, not broker contracts.
- Account-currency risk sizing not verified (price-distance units only).
- Phase 8 controlled discovery intentionally not used to optimize into a pass.

## Artifacts

- `scripts/variant_bv_engine.py`
- `docs/SOURCE_AUDIT.md`, `ACCEPTANCE_REPORT.md`
- `reference/` original rulebooks, summaries, trades
- `outputs/dataset_inventory.csv`, `transfer_results.csv`, GBPUSD causal trade CSVs
- `tests/test_causal_engine.py` (3 PASS)

## Next step

Do **not** expand parameters on this hypothesis to chase the look-ahead reference P&L. If revisited, require independent preregistered trade-management and Class A costs with frozen causal rules — or close as negative.
