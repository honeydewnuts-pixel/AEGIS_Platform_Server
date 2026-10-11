# AEGIS Coordinated Next-Phase Plan (Stage 6.6 continuation)

**Main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Docs branch:** `stage-6.6-operational-integrity`  
**Stage 6.6 acceptance:** **INCOMPLETE** — not PASS

## Priority order

| # | Action | Responsible | Prerequisites | Evidence required | Acceptance criteria |
|---|--------|-------------|---------------|-------------------|---------------------|
| 1 | **Preserve** Neon temp branch evidence before expiry (~2026-10-12) | Owner / operator | Access to Neon console | Saved SELECT outputs (alembic, counts, queue signal_id status) with branch names | Notes stored offline; branches may expire after |
| 2 | **Production read-only inventory** | Operator | Neon production SQL Editor | Results of `AEGIS_PRODUCTION_INVENTORY_RUNBOOK.md` Q1–Q9 | All queries run on **production**; results timestamped |
| 3 | **Executor presence + deployed commit** | Operator | Admin API key; Render dashboard | `executor-status` JSON; full Render deploy SHA | Presence interpreted per verification doc; SHA recorded |
| 4 | **Live lifecycle / portfolio-risk review** | Owner + Builder (docs only until authorized) | Inventory results | Q5–Q7 + MT5 open-position list | Discrepancies listed; no auto-repair |
| 5 | **Isolated recovery test** | Operator | Neon create-branch or external restore | Checklist in recovery acceptance criteria | Stage 6.6 recovery may move toward PASS only if checklist met |
| 6 | **Review diagnostic docs branch** | Owner | GitHub access | Branch `stage-6.6-operational-integrity` | Explicit merge approval if desired (separate) |
| 7 | **Reassess acceptance gates** | Owner | Items 1–5 evidence | Written gate matrix | No PASS without evidence |

## Hard stops until evidence arrives

- No new controlled-demo signal.  
- No force of UUID `9fc3cb49-d6eb-4aa4-a4e5-4f75ee10f37b`.  
- No production deploy / migration / EA install.  
- No Rulebook promotion; V53.6 remains frozen.  
- `production_authorized` remains false.

## Related documents on this branch

- `AEGIS_OPERATIONAL_BASELINE_REPORT.md`
- `AEGIS_EXECUTION_QUEUE_ROOT_CAUSE_REPORT.md`
- `AEGIS_MT5_COMPONENT_HEALTH_REPORT.md`
- `AEGIS_SIGNAL_AND_HOLD_DIAGNOSTIC.md`
- `AEGIS_STAGE_6_6_DATABASE_RECOVERY_ACCEPTANCE_REPORT.md`
- `AEGIS_POSITION_LIFECYCLE_AND_RISK_INTEGRITY_REPORT.md`
- `AEGIS_PRODUCTION_INVENTORY_RUNBOOK.md` *(this continuation)*
- `AEGIS_EXECUTOR_PRESENCE_VERIFICATION.md` *(this continuation)*
- `AEGIS_STAGE_6_6_RECOVERY_ACCEPTANCE_CRITERIA.md` *(this continuation)*
