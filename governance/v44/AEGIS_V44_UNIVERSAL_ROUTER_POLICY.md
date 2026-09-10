# AEGIS V44 Universal Router Policy

## Route states
- `RESEARCH_ONLY`: research result may be recorded; execution authorization = false.
- `QUALIFIED_PAPER`: qualified rulebook/model may generate paper intent; live authorization = false.
- `PRODUCTION_ELIGIBLE`: reserved for a future checkpoint after explicit qualification and acceptance gates.
- `FAIL_CLOSED`: missing/invalid lineage, stale data, unsupported instrument/timeframe, risk violation, or authorization mismatch.

## V43 handling
V43 model status = `RESEARCH_ONLY`.
V43 threshold = `0.6000000000000003` (locked from Validation).
No threshold retuning occurs in V44.

## Non-negotiable rule
`research_signal && !production_qualified => no_live_order`

A neural prediction cannot bypass a rejected/unqualified rulebook, risk gate, stale-data gate, spread gate, position limit, kill switch, or explicit production authorization.
