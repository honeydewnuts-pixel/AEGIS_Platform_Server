# V31 / V53.6 Live Position Manager (Executor v2.19)

## 72-bar window (aligned with `simulate_short`)

Historical (`common.py`):
- Signal on bar `i`
- Entry at AskOpen of bar `i+1`
- Loop `j` from `i+1` to `i+72` **inclusive**
- TIME exit at close of bar `i+72` if no earlier STOP

→ **72 holding bars**, entry bar counts as bar 1.

| Layer | TIME condition |
|-------|----------------|
| Python | `(bar_index - entry_bar_index + 1) >= max_hold_bars` |
| MQL5 | `HoldingM5BarsInclusive(symbol, entryTime) >= maxHold` via `iBarShift` |

Stop is checked **before** TIME on the same bar (historical order).

## Other rules (unchanged from v2.18)
- BE / trail only after **confirmed** broker SL
- Frozen initial risk; no invent on incomplete state
- Short-only baseline
- Production authorization disabled

## Live vs historical
Entry = fill (not AskOpen); broker costs (not 0.085R); M5 rates as Bid proxy.
