# AEGIS Position Lifecycle and Portfolio Risk Integrity Report

**Main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Basis:** Source inspection + main CI (Stage 6.4A/B tests). **Not** a live production portfolio audit.

## Implementation summary

| Area | Design on main |
|------|----------------|
| Lifecycle | `AegisPositionLifecycle` + durable lifecycle service |
| Open risk flag | `open_risk_applied` NULL / FALSE / TRUE (migration 0023) |
| Portfolio risk | `subscriptions.open_risk_usd` via `PortfolioRiskService` |
| ACK path | Durable ACK ordering; mark applied only with successful risk record in same transaction intent |
| Reconcile | FOR UPDATE; concurrent recovery tests on CI |
| Queue | Claim / SUBMISSION_UNCERTAIN; no auto-redeliver |

## Checklist vs source design

| # | Question | Source-level assessment |
|---|----------|-------------------------|
| 1 | Open records initial risk | Designed via `risk_usd_at_open` on lifecycle |
| 2 | Reflected in portfolio | `record_open_risk` |
| 3 | No double-count | Tri-state flag + tests |
| 4 | Release once on close | `release_open_risk` + concurrent release tests |
| 5 | Partial / broker-side close | Depends on Executor close notifications + reconcile — **runtime UNVERIFIED** |
| 6 | Missing ACK | Can leave PENDING/CLAIMED/UNCERTAIN; risk not applied until confirmed path |
| 7 | Idempotent reconcile | Designed + PG tests |
| 8 | Concurrent no double-release | CI PG tests **PASS** |
| 9 | BUY and SELL | Direction fields present; EA LONG PM was prior remediation theme — **runtime UNVERIFIED** |
| 10 | Broker/server disagree | Fail toward reconcile / uncertain; no silent invent |
| 11–12 | Risk limits before authorize | Portfolio risk service exists; **live limit breach behavior UNVERIFIED** this session |
| 13 | Demo ≠ production | Separate flags; controlled_demo methodology gate |
| 14 | Withdrawal design | Spec documented historically; **implementation authorization separate** — not audited as production-enabled here |

## Withdrawal design (owner-stated — not activated here)

- No withdrawal before equity ≥ 2× starting balance  
- Then 30% withdraw / 70% reinvest of eligible profit  
- Cap-sweep only per approved rulebook  

**This diagnostic does not implement or change withdrawal behavior.**

## Production inventory still required

Live row counts for lifecycle `open_risk_applied` distribution and `open_risk_usd` remain **UNVERIFIED** without operator Neon SELECT on **production**.

## Status

**Source/CI integrity of Stage 6.4 risk recovery: PASS (design + automated tests).**  
**Live production risk ledger: UNVERIFIED.**  
**Exactly-once broker execution: not claimed.**
