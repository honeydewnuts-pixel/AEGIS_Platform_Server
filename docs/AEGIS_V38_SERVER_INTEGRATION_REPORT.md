# AEGIS V38 Server Integration Report

## V38-SERVER-03 result

**PASS WITH MACHINE-PRECISION DIFFERENCE**

V38-SERVER-02's ledger-oracle limitation has been removed. V31 and V35 are now independently evaluated by server-side causal evaluators against the V37 standardized dataset.

## Reference integrity

Dataset: `AEGIS_V37_STANDARDIZED_GBPUSD_5M.csv`

SHA-256: `6e962ec23023f9c747514bed17077a9bc7dadc4b42591feb1e29140c1e580ed5`

The evaluator validates the SHA-256 and chronological monotonicity before execution.

## Results

### V31

- Signal population: 2,825 — exact.
- Completed trades: 2,600 — exact.
- Trade event sequence: exact.
- Entry/exit/reason/duration sequence: exact.
- PF: server 1.4803553737250508 vs reference 1.4803553737250497.
- Average R: server 0.2350972165879110 vs reference 0.2350972165879105.
- Total R: server 611.2527631285685 vs reference 611.2527631285673.
- Maximum DD: server 26.205311475506573 vs reference 26.20531147550692.
- Maximum numerical field difference: 4.418687638008123e-13.

### V35

- Signal population: 2,238 — exact.
- Completed trades: 2,060 — exact.
- Trade event sequence: exact.
- Entry/exit/reason/duration sequence: exact.
- PF: server 1.7018831432004442 vs reference 1.7018831432004435.
- Average R: server 0.3278296899489546 vs reference 0.3278296899489543.
- Total R: server 675.3291612948465 vs reference 675.3291612948458.
- Maximum DD: server 12.144862042607272 vs reference 12.144862042607272.
- Maximum numerical field difference: 3.064215547965432e-13.

## Why this is not an exact-bit PASS

The recovered server evaluator uses the same mathematical recurrence but performs calculations through its own NumPy/Pandas execution path. The remaining differences are machine-precision floating-point differences only; event indices, trade sequence, exits, reasons, and aggregate behavior are unchanged.

## Final Test governance

No evaluator parameter was selected or tuned against Final Test. Final Test remains locked. The V37 reference ledgers are comparison-only artifacts.

## Existing platform preservation

The existing RULEBOOK_V3, Neural V3 assets, signal engines, fallback engines, MT5 worker/adapter, existing APIs, database architecture, migrations, clients, Docker configuration, and execution safeguards were preserved.

## Live execution

Disabled for this checkpoint.
