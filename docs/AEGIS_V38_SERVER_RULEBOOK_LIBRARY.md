# AEGIS V38 Server Rulebook Library

V38-SERVER-02 introduces a versioned Rulebook Registry without replacing the existing RULEBOOK_V3 or Neural V3 infrastructure.

Founding frozen research rulebooks:
- `AEGIS-RB-V31-GBPUSD-5M`
- `AEGIS-RB-V35-GBPUSD-5M`

This checkpoint is historical-replay only. Registration is not production authorization.
Unknown or unqualified lookup must fail closed with `NO_QUALIFIED_RULEBOOK`.

The replay adapter verifies the SHA-256 of the V37 standardized dataset and uses the frozen V37 reproduction ledgers as the exact historical oracle. This preserves the established research baseline while leaving the execution interface ready for a fully causal server-side evaluator in a subsequent hardening checkpoint.
