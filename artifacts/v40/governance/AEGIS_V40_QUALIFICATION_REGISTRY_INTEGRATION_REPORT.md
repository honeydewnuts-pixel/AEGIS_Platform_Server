# AEGIS V40 — Qualification & Universal Rulebook Registry Integration

Date: 2026-09-09
Status: IMPLEMENTED — RESEARCH GOVERNANCE CHECKPOINT

## Scope
This checkpoint converts the completed V39 empirical audit into explicit, versioned registry and routing policy artifacts. It does not authorize live trading.

## Qualified V39 transfer family
Six instrument/rulebook combinations passed the immutable V39 qualification gates:
- AUDUSD: V31 and V35
- USDCHF: V31 and V35
- NZDUSD: V31 and V35

Each has Validation >=300 trades and PF >1.60, Final Test >=300 trades and PF >1.60, six-block PF >1, causal/execution audit pass, and independent reproduction.

## Rejected / disabled cohort
- EURUSD: transfer rejected; native discovery required.
- USDJPY: transfer rejected; trading disabled; native discovery required. No synthetic Ask/spread data is permitted.
- EURJPY: native discovery rejected because the best screened candidate had 195 Validation trades, below the immutable 300-trade gate.
- GBPJPY: native discovery rejected because the selected candidate failed PF gates.

## Legacy preservation
RULEBOOK_V3 remains intact and separately identified. V39 rulebooks do not replace it. The router is fail-closed and cannot substitute an unrelated rulebook when an instrument is unqualified.

## Production authorization
No V39 candidate is production-authorized by this checkpoint. Historical qualification and production authorization remain separate governance states.

## V40 exit criteria
- Registry entries created for all currently evaluated V39 instruments: PASS
- Six qualified transfers explicitly registered: PASS
- Failed instruments explicitly disabled: PASS
- Universal Router policy defined: PASS
- Legacy RULEBOOK_V3 preservation: PASS
- Production authorization remains closed: PASS
- V43 neural lineage remains separate from legacy neural V3: PASS

## Next stage
V41 should be a controlled forward/paper-validation and operational replay checkpoint for the qualified family, using only data after the frozen historical cutoff. No parameter retuning is allowed in V41.
