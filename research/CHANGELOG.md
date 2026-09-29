# Research changelog

## 2026-09-28 — Initial USDCHF research handoff import

- Imported AEGIS_RESEARCH_HANDOFF_2026-09-28 package into `research/`.
- Preserved existing `research/v43/` neural research materials (untouched).
- Verified SHA-256 for all 10 package artifacts against package `SHA256SUMS.txt`.
- Documented open VPS/Demo incident from mobile screenshots (not resolved).
- Established integration register: no research feature marked Server-integrated.
- **No operational Server runtime, rulebooks, Feed, or Executor code changed.**

### Artifact inventory (verified)

| File | Bytes | SHA-256 (prefix) |
|------|------:|------------------|
| USDCHF_M5_BIDASK_5Y.csv | 38311813 | f93d6440… |
| USDCHF_V53_6_cash_test_ledger.csv | 48616611 | 104598a6… |
| USDCHF_V53_6_autonomous_assessment_cash_ledger.csv | 49856456 | da2a27e1… |
| USDCHF_V53_6_operational_replay_ledger.csv | 930933 | c288d162… |
| + 4 smaller CSVs and 2 screenshots | (see SHA256SUMS.txt) | OK |

### Known research limitations (documented, not “fixed” by this import)

- Original cash-test ledger does not cover every requested starting balance.
- Small-account diagnostic is summary-only.
- Cap-sensitivity results differ from original at higher risk levels.
- Full requested matrix: 7 balances × 7 risk % × 3 leverages × 6 horizons = 147 scenarios — **not claimed complete**.
