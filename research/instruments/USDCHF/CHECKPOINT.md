# USDCHF Research Checkpoint — 2026-09-28

**Status:** OPEN; cash-test reconciliation incomplete. **Final Test:** LOCKED for selection/qualification. Full-history results are diagnostic only. **Server integration:** NOT CONFIRMED.

## Frozen V53.6 operational reference
Short-only; next-bar Ask entry; Bid exits; ATR(14); initial stop 1.5 ATR; break-even at +1R; trailing stop 0.75 ATR; maximum holding period 72 bars. Bid/Ask costs are embedded in execution prices (`bid_ask_embedded_v1`). Do not add a universal fixed 0.085R cost or double-count spread. Any alternative entry/exit method must be separately versioned and qualified.

## Dataset
`USDCHF_M5_BIDASK_5Y.csv`; previously audited at 373,551 rows, from 2021-09-15 23:00 UTC to 2026-09-15 23:00 UTC. Previously observed 484 gaps greater than five minutes and no duplicate/null issues in audited columns. Verify the included SHA-256 manifest before reuse.

## Existing full-history operational replay (diagnostic only)
Previously reported: 5,386 signals; 4,957 completed trades; 2,982 wins; 1,975 losses; 60.16% win rate; PF 2.653; average 0.658R; cumulative 3,259.91R; maximum drawdown 11.39R. This is not a qualification result and must not be used to select a champion while Final Test is locked.

## Existing cash artifacts and limitations
- Original cash ledger: 138,796 rows, 28 scenarios = $500/$1,000/$5,000/$10,000 × seven risk levels. It lacks event-level ledgers for $50/$100/$250.
- Separate small-account diagnostic: summary-only for $50/$100/$250 × seven risks × two lot models; not a fully reconciled event-level replay.
- Original rejection status combines minimum-lot and margin rejection (`REJECTED_MIN_LOT_OR_MARGIN`), so the cause of each rejection is not independently identified.
- Cap-sensitivity summary differs from the original at high risk and is not an exact reproduction.
- Prior arithmetic audit found equity roll-forward consistency, but that alone does not validate sizing/margin assumptions or explain every rejection.

## Requested cash matrix
Balances: $50, $100, $250, $500, $1,000, $5,000, $10,000. Risks: 0.05%, 0.1%, 0.25%, 0.5%, 1%, 2.5%, 5%. Leverage: 100:1, 500:1, 1,000:1. Total: **147 scenarios**. Periods: 1 day, 1 week, 1 month, 6 months, 1 year, 5 years.

Use chronological compounding; recalculate risk budget from current equity after each completed gain/loss; rejected trades do not change equity. Leverage affects margin requirement, not stop-loss risk for fixed position size. Explicitly document contract size, account-currency conversion, minimum lot, volume step, and margin model; do not invent broker-specific values.

## VPS/Demo evidence (2026-09-28 screenshots)
Home screen reports ONLINE/LIVE, `CAPTURE_COMPLETE`, confidence 0%, HOLD reason `CONFIDENCE_BELOW_THRESHOLD`, threshold 0.55, worker connected, next capture in 285 seconds, V31 short baseline says no entry on latest closed bar (`event_throttle`), pair NZDCHF M5, path `v40_research_ohlc`, router `ROUTABLE_RESEARCH`, rule `AEGIS-RB-V53.6-V31-NZDCHF-5M`. Alerts screen shows 0 unread, subscription-ended notices, and older NZDJPY SELL demo-structure alerts; the alert says production authorization remains false.

These are observations only. They do not prove a backend fault, healthy processing, or an executed order. The accidental-trigger concern remains unresolved pending MT5 positions/history and backend/feed/analysis/executor/notification logs.

## Next actions
1. Builder inspects live repository and HEAD, imports package without modifying Server runtime, verifies hashes, commits/pushes, and reports exact paths and commit.
2. Check MT5 positions/history and VPS logs before resuming autonomous tests.
3. Reconcile existing cash ledgers and sizing/margin assumptions; label any new implementation as reconstruction until validated.
4. Continue USDCHF only; preserve Final Test lock.
