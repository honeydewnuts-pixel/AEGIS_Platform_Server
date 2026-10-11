# Stage 6.6 Recovery Acceptance Criteria

**Status of Stage 6.6 overall: INCOMPLETE** (do not mark PASS until all required evidence exists)

## Explicit rule

**Creating a Neon historical or PITR-style branch is not sufficient proof of an independent backup/restore test.**

Branch/copy-on-write shows Neon can materialize a point-in-time dataset. Acceptance requires a **documented, isolated recovery exercise** with recorded outcomes.

## Required evidence checklist

| # | Evidence | Required |
|---|----------|----------|
| 1 | **Recovery source** identified (branch parent, PITR timestamp, or external dump id) | Yes |
| 2 | **Timestamp** of recovery source and of verification | Yes |
| 3 | **Isolated restoration** target (disposable branch or non-production database) | Yes |
| 4 | Confirmation production branch was **not** overwritten | Yes |
| 5 | **Schema / migration** check: `alembic_version` matches expected head for that source | Yes |
| 6 | Critical tables present: `aegis_execution_queue`, `aegis_position_lifecycle`, `subscriptions`, `aegis_operational_control`, `aegis_executor_presence` | Yes |
| 7 | Non-secret **row counts** recorded for those tables | Yes |
| 8 | `open_risk_applied` column exists and is nullable boolean (if source ≥ 0023) | Yes |
| 9 | **Application compatibility** note: restored schema usable for read-only app checks (optional deeper test) | Preferred |
| 10 | **Lifecycle / portfolio-risk** consistency spot-check (no auto-repair) | Preferred |
| 11 | **Separation** from broker execution (no Executor pointed at recovery DB for trading) | Mandatory |
| 12 | Backup **retention / RPO** statement for the Neon plan or external backup | Preferred for ops policy |

## What already counts (partial)

- Historical branch showed Alembic `0023_lifecycle_open_risk_applied` and nullable `open_risk_applied` → **schema consistency at that point** only.  
- Sparse row counts on a historical branch → **not** a substitute for production inventory.

## What still blocks PASS

- No completed disposable recovery verification with full checklist recorded.  
- Neon Backup & Restore UI blank → backup product path **UNVERIFIED**.  
- Temporary branches may **expire** — export evidence before loss.

## Pass statement (only when true)

Stage 6.6 recovery acceptance may be marked **PASS** only when items 1–8 and 11 are evidenced and reviewed, and production remains untouched by the test.
