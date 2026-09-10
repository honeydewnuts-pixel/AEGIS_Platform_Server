# AEGIS V44 — Neural + Rulebook + Universal Router Integration Architecture

Version: V44.0
Status: ENGINEERING COMPLETE — PRODUCTION AUTHORIZATION FALSE

## Purpose
V44 integrates the V43 neural research lineage with the V40 Rulebook Registry/Universal Router and V42 execution-risk-safety boundary. V43 remains RESEARCH_ONLY.

## Decision hierarchy
1. Validate market-data freshness and instrument/timeframe identity.
2. Resolve eligible rulebooks from the V40 registry.
3. Evaluate frozen rulebook signal(s).
4. If a V43 neural model is requested, load only the immutable V43 model lineage and verify model/schema/version hashes.
5. Neural output may be used as research evidence, confidence/context, or a veto/confirmation according to an explicitly versioned policy; it may not independently authorize execution.
6. Pass the resulting intent through V42 risk and safety gates.
7. Execution is permitted only when an explicitly qualified production model/rulebook and all safety gates are present. Otherwise FAIL_CLOSED.

## Current V44 policy
Because V43 is RESEARCH_ONLY, the V43 neural signal is **non-authorizing**. For the current checkpoint it can produce a research decision record but cannot create an executable order intent.

## Legacy isolation
RULEBOOK_V3 and legacy Neural V3 remain intact. V43 is a separate model lineage and is never silently substituted for the legacy model.

## Final Test governance
V43 Final Test remains locked. V44 does not retune the V43 model or its threshold.
