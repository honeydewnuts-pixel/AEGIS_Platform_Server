# Conformance Matrix — Frozen v2.1 vs Prior DBT RSI V1 Implementation

**Base branch/commit:** research/dbt-rsi-reversal-v1-20261020 @ 94b50e7  
**This branch:** research/bb17-bb34-rsi-swing-v2.1-20261021  

**Note:** Full uploaded document "BB17/BB34 RSI Swing Rulebook — frozen research specification v2.1" and reference engine "BB17-BB34-RSI-SWING-M5-V2.1" were **not found** as files in the repository. Conformance uses the **explicit rules stated in the research task**, which supersede prior DBT V1 where they differ.

| # | Rule | Frozen v2.1 (task) | Prior DBT V1 (94b50e7) | Match? | Difference / consequence | Corrective action |
|---|------|--------------------|------------------------|--------|--------------------------|-------------------|
| A | BB34 on Close | period 34, dev 1.000 | period 34, dev 1.000 | YES | — | Keep |
| B | BB17 on Close | period 17, dev 1.000 | period 17, dev 1.000 | YES | — | Keep |
| C | Rolling stdev | **ddof=0** (population) | **ddof=1** (sample) | **NO** | Band width differs; thresholds shift | Switch to ddof=0 |
| D | RSI9 Wilder | Exact Wilder init + recursion | Wilder seed mean first period then recurse | PARTIAL | Seed detail may differ by 1 bar | Align to task-stated Wilder; document |
| E | SMA7 on RSI9 | SMA(7) of RSI9 | SMA(7) of RSI9 | YES | — | Keep |
| F | Lower BB 1.618 | **BB34 dev 1.618 on SMA7(RSI9)** | BB34 1.618 **on RSI9 directly** | **NO** | Core dependency chain wrong; RBB levels differ | **Rebuild RBB on SMA7** |
| G | WPR60 | Diagnostic only; no trade gate | Diagnostic only; rate vs RBB_U ~0 | YES | — | Keep diagnostic |
| H | Warm-up | Indicators ready after max period | NaN until period filled | YES | — | Keep |
| I | Initial contexts | Bullish/bearish from BB structure | UPTREND/DOWNTREND from B17_U>B34_U / B17_L<B34_L | PARTIAL | Need exact initial-entry rules from full doc | Document provisional context = established band structure |
| J | RSI swing confirm | Confirmed swing; no pre-right-side confirm | L=2 R=2 provisional | PARTIAL | Params provisional | Keep L=2 R=2 labeled PROVISIONAL unless doc specifies |
| K | Early reversal | RSI zone + prior excursion; independent of main weaken | Same intent | YES | Band values were on wrong series (F) | Fix series then re-run |
| L | Late structural | B17_M/B34_M cross + sequence | Incomplete in V1 | PARTIAL | Spec gaps remain | Implement explicit late rules when fully specified; otherwise mark blocked |
| M | Position/conflict | One position; opposing = hold | Event logging only | PARTIAL | V1 was signal-only | Add target-state machine without inventing cash rules |
| N | Decision timestamps | Signal at confirm; fill ref = next open | Confirm at extreme+R | YES for confirm lag | Need next-open annotation | Annotate next bar open as execution reference |
| O | Missing/EOF | No fabricated fill | NaN outcomes at EOF | YES | — | Keep |

## Critical corrections required

1. **ddof=0** for all Bollinger stdev.  
2. **RBB on SMA7(RSI9)**, not RSI9.  
3. Re-run signals after (1)(2); prior V1 eligible counts are **not** v2.1-conformant.
