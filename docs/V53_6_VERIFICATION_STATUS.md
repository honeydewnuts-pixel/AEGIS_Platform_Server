# V53.6 Verification Status

## Dataset
- File: `USDCHF_M5_BIDASK_5Y.csv`
- SHA-256: `f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97` **VERIFIED MATCH**
- Rows: 373551

## Event generation
- Source: `backend/app/rulebooks/evaluators/v31_gbpusd_5m.py` (V31 SHORT filters applied to USDCHF)
- Lineage: V31 GBPUSD source → V53.6 transfer/normalization → USDCHF target
- Events reproduced: **5386** signals; **4957** trades (one-position constraint)

## Locked comparison vs `USDCHF_V53_6_operational_replay_ledger.csv`
- Matched event_i: **4957 / 4957**
- Only reproduced / only artifact: **0 / 0**
- Entry/exit/R diffs: **0** (within float noise)

## Metrics (full-sample historical path)
| Path | Trades | PF | total R |
|------|--------|-----|---------|
| Legacy 0.085R | 4957 | ~2.327 | ~2839 |
| Bid/Ask only (no 0.085R) | 4957 | ~2.653 | ~3260 |
| Rulebook validation (split) | 729 | 2.387 | — |
| Rulebook final test (split) | 735 | 2.375 | — |

## Classification

**VERIFIED** — independent reconstruction of the V31-on-USDCHF event stream and trade ledger matches the operational replay artifact event-for-event under the frozen historical convention (AskOpen entry, BidHigh stop, optional 0.085R).

This does **not** authorize production trading. Production remains gated separately.

## Cash matrix
**NOT VERIFIED** — incomplete existing summary; regeneration deferred until after this verification (now available for a follow-on).

## Artifacts
- `artifacts/v53_6_verification/USDCHF_V53_6_REPRODUCTION_SUMMARY.json`
- `artifacts/v53_6_verification/USDCHF_reproduced_trades_*.csv`
