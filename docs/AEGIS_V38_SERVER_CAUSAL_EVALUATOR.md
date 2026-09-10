# AEGIS V38-SERVER-03 — Causal Rulebook Evaluator

## Status

**V38-SERVER-03: PASS WITH MACHINE-PRECISION DIFFERENCE**

The server now independently evaluates the frozen V31 and V35 rulebooks from the standardized V37 market dataset. The V37 ledgers are used only by the comparison harness as frozen reference oracles and are not used by the evaluator to generate signals or trades.

## Implementation recovery

The exact research implementations were recovered from the local V31 qualification package (`run_v31.py`) and V35 progressive-discovery package (`run_v35.py` / `run_v35_independent.py`). This resolved the earlier discrepancy caused by an abbreviated reconstruction of the rules.

A critical recovered V31 detail is preserved: the 12-bar qualifying-down-break throttle advances before the subsequent exhaustion/compression filters. This is required to reproduce the frozen 2,825-event population.

For V35, the exact frozen finalist implementation is the `MULTI_SCALE_AGREE_L12_DOWN_SHORT` state: prior 12-bar compression < 1.0, current expansion >= 1.5 ATR, negative 24-bar close displacement, negative 48-bar close displacement, and a 12-bar event throttle.

## Server modules

- `backend/app/rulebooks/evaluators/common.py` — canonical dataset validation, frozen ATR recurrence, execution simulator and metrics.
- `backend/app/rulebooks/evaluators/v31_gbpusd_5m.py` — causal V31 evaluator.
- `backend/app/rulebooks/evaluators/v35_gbpusd_5m.py` — causal V35 evaluator.
- `backend/app/rulebooks/causal.py` — rulebook evaluator facade with fail-closed unknown-rulebook behavior.

## Causality

Features are calculated from completed bars at or before the signal bar. Entry is the next bar's AskOpen. No future trade outcomes, future prices, Final Test selection, or reference-ledger data are read by the evaluator.

## Execution

The recovered frozen execution model is preserved: 1.5 ATR initial stop, +1R break-even, 0.75 ATR trailing after break-even, BidHigh stop trigger for shorts, 72-bar maximum hold, 0.085R cost, and one position at a time.

## Reproduction

The server-generated trade ledgers match the V37 reference event/trade sequence exactly. Price/R fields differ only by floating-point arithmetic at approximately 1e-13 or less.

| Rulebook | Signals | Trades | Max numeric difference | Result |
|---|---:|---:|---:|---|
| V31 | 2,825 | 2,600 | 4.42e-13 | PASS |
| V35 | 2,238 | 2,060 | 3.06e-13 | PASS |

Aggregate statistics reproduce within the same machine-precision tolerance.

## Testing

The causal evaluator test suite was run independently of the repository's database-dependent `tests/conftest.py`:

`3 passed in 2.86s`

The broader repository pytest collection remains **BLOCKED** in the current environment because the pre-existing test configuration imports `asyncpg`, which is not installed. This dependency was not altered or masked.

## Live-trading safety

This checkpoint is historical replay only. No live trading, broker execution, or production authorization was performed.
