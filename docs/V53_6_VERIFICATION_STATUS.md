# V53.6 Verification Status

## Classification (precise)

### REPRODUCTION VERIFIED

The current V31-on-USDCHF reconstruction **matches the stored repository ledger**  
`USDCHF_V53_6_operational_replay_ledger.csv` event-for-event:

- Dataset SHA-256: `f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97` (match)
- Rows: 373551
- Signals: 5386 → trades: 4957
- Matched event_i: 4957/4957; entry/exit/R delta: 0
- Legacy PF ≈ 2.3265; Bid/Ask-only PF ≈ 2.6532

This proves **internal consistency** of the reconstruction against the **stored operational ledger**.

### ORIGINAL RESEARCH INDEPENDENTLY VERIFIED

**Not claimed.** Independent original research event-generation evidence (outside treating the stored operational ledger as reference truth) was not separately established in this checkpoint.

## Methodology

Frozen historical path unchanged (AskOpen entry, BidHigh stop, 0.085R optional for legacy reproduction).

## Production

`production_authorized = false` — reproduction verification is **not** production authorization.
