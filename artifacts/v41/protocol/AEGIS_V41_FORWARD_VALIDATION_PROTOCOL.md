# AEGIS V41 — Controlled Forward / Paper Validation Protocol
Version: V41.0
Date: 2026-09-09
Status: DEFINED — NO_NEW_DATA

## Purpose
V41 validates the six V39-qualified research transfer candidates in sequential forward/paper mode without changing their parameters. It is an operational validation stage, not a historical optimization stage.

## Frozen candidates
- AUDUSD V31
- AUDUSD V35
- USDCHF V31
- USDCHF V35
- NZDUSD V31
- NZDUSD V35

## Forward boundary
Historical research data ends at 2026-08-28 16:55:00 in the governing V39 datasets. V41 forward observations must begin strictly after that timestamp.

## No-retuning rule
No V31/V35 parameter, threshold, risk parameter, entry rule, exit rule, cost assumption, or selection criterion may be modified using forward observations.

## Required live/paper inputs
For each instrument/timeframe:
- timestamped M5 Bid OHLC
- Ask OHLC or independently documented executable spread
- broker/source identity
- timezone/clock provenance
- sequence continuity
- duplicate and integrity checks

## Signal and execution sequence
1. Receive completed M5 bar.
2. Calculate only causal features.
3. Evaluate the frozen rulebook.
4. If qualified, queue next-bar entry.
5. Use instrument-appropriate Bid/Ask execution side.
6. Apply frozen 1.5 ATR initial stop, +1R break-even, 0.75 ATR trailing and 72-bar maximum.
7. Record every signal, accepted/rejected paper order, fill assumption, stop/trailing event and exit.

## Forward governance gates
V41 does not replace V39 qualification. It measures forward behavior and operational integrity. It records:
- data integrity
- causal timing
- signal count
- paper trades
- realized R
- PF when sample permits
- drawdown
- execution/slippage observations
- rulebook stability
- router eligibility decisions
- anomalies

No minimum PF is used to retroactively requalify or retune the frozen rulebooks during V41.

## Production safety
V41 is paper validation only. Production authorization remains FALSE. Universal Router must fail closed if a qualified rulebook, instrument, timeframe, data side, or execution state is unavailable.
