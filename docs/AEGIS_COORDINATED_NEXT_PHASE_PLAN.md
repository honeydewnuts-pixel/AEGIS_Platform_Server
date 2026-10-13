# AEGIS Coordinated Next-Phase Plan

**Last Builder verification:** 2026-10-13  
**Main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Docs branch HEAD:** `e46506d08e314cc5a0cbbdbaf7ed7ef6f7f0c0f7` (+ this commit)  
**Stage 6.6:** **INCOMPLETE**

## Current verified facts

- Main and docs branch SHAs verified; all 11 Stage 6.6 diagnostic/runbook files exist.  
- CI green on main `f546af7`.  
- Live API health contract matches post–health-route deploy (`3.0.3`, Redis ok).  
- Production inventory, Executor presence, MT5 runtime, full recovery acceptance: **still operator-dependent**.

## Priority order

| # | Action | Who | Prerequisite | Done when |
|---|--------|-----|--------------|-----------|
| 1 | Confirm Neon temp branches; export any remaining evidence | Operator | Neon console | Notes saved offline or “expired / gone” recorded |
| 2 | Production inventory (runbook Q1–Q9) | Operator | Neon **production** SQL Editor | Results in evidence package |
| 3 | Executor-status API + full Render SHA | Operator | Admin key; Render dashboard | JSON + SHA recorded |
| 4 | Optional MT5 Experts snapshot | Operator | VPS | Feed/Executor version and errors noted |
| 5 | Evidence review | Builder (next authorized session) | Package from 1–4 | Updated gate matrix; no production writes |
| 6 | Isolated recovery test (if still needed for PASS) | Operator | Neon create-branch or external backup | Recovery criteria checklist complete |
| 7 | Docs branch merge | Owner only | Explicit approval | Separate decision |
| 8 | Controlled Demo / deploy | Owner only | Gates satisfied | Separate authorization each |

## Acceptance reminders

- Do **not** mutate signal `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b`.  
- Do **not** mark Stage 6.6 PASS without recovery checklist evidence.  
- Do **not** promote Rulebooks or change V53.6.  
- Green CI ≠ production trading readiness.

## Primary runbooks

- `docs/AEGIS_PRODUCTION_INVENTORY_RUNBOOK.md`  
- `docs/AEGIS_EXECUTOR_PRESENCE_VERIFICATION.md`  
- `docs/AEGIS_STAGE_6_6_RECOVERY_ACCEPTANCE_CRITERIA.md`  
- `docs/AEGIS_STAGE_6_6_STATUS_AND_OPERATOR_EVIDENCE_PACKAGE.md`
