# AEGIS V38 Server Changelog

## V38-SERVER-03

- Recovered exact V31 research implementation from the V31 qualification package.
- Recovered exact V35 finalist implementation from the V35 discovery/independent reproduction packages.
- Added server-side causal evaluator facade.
- Added shared V37 dataset verification and frozen ATR14 recurrence.
- Added independent server execution of the frozen short execution model.
- Added V31 and V35 causal replay ledgers.
- Added reference-comparison artifacts.
- Added causality/execution reproduction audit.
- Added causal evaluator unit tests.
- Removed dependence on the V37 ledger from the evaluator execution path.
- Kept the existing V38 reference replay adapter intact for historical compatibility; it is no longer the source of truth for V38-SERVER-03 causal evaluation.
- Live trading remains disabled.
