# ARRS Candidate Lifecycle Specification

## States (provisional)

1. DISCOVERED — candidate definition recorded; no evaluation required yet  
2. SCREENED — support/integrity filters applied  
3. VALIDATION_PENDING — prereg recorded; evaluation queued  
4. VALIDATED — passed preregistered validation criteria (research-only)  
5. DEMO_ELIGIBLE — human/review gate; still not live  
6. DEMO_QUALIFIED — demo criteria met under separate policy  
7. APPROVED — explicit production authorization actor (outside ARRS auto-path)  
8. DEGRADED — monitoring indicates material deterioration  
9. SUSPENDED — temporary halt of signals for this Rulebook  
10. RETIRED — permanent withdrawal  
11. REJECTED — failed gates; record retained  

## Transition rules (selected)

| From | To | Required evidence | Actor |
|------|-----|-------------------|-------|
| DISCOVERED | SCREENED | Support metrics, data hashes | Research system |
| SCREENED | VALIDATION_PENDING | Prereg document hash | Research system |
| VALIDATION_PENDING | VALIDATED | Metrics vs prereg thresholds | Research system |
| VALIDATION_PENDING | REJECTED | Failure reason codes | Research system |
| VALIDATED | DEMO_ELIGIBLE | Review checklist | Authorized human role |
| DEMO_ELIGIBLE | DEMO_QUALIFIED | Demo policy evidence | Authorized human role |
| DEMO_QUALIFIED | APPROVED | Production authorization record | Production authority (not ARRS) |
| * | REJECTED | Reason code; immutable prior state history | Research or human |
| APPROVED | DEGRADED/SUSPENDED/RETIRED | Monitoring evidence + policy | Risk/ops authority |

**Forbidden:** any transition to APPROVED initiated solely by ARRS evaluation score.  
**Forbidden:** overwriting REJECTED records; reconsideration creates a **new version** linked to parent_id.

## Rollback

APPROVED → previous APPROVED version requires explicit supersedes link and authorization event. ARRS may **recommend** but not execute production rollback.
