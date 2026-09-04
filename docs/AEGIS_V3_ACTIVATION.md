# AEGIS v3 Activation Baseline

Effective: 2026-08-31

The production analysis path is v3-only:
- Indicator stack: v3 (BB34 #7, BB17 #8, RSI9 #6, MA7 #4, BB34 #1).
- Rulebook: RULEBOOK_V3 v2.3.6.6.
- Rule engine: `SignalRuleEngineV3`.
- Neural: `AEGIS Neural v3 2.3.6.6 teacher-confidence` (13 features).

Legacy v1/v2 indicator stacks, rulebooks, neural models, and legacy rule-engine
source are archived under `archive_v1_v2/` and are not loaded by the active path.

The deterministic v3 rule engine is authoritative. Neural v3 may adjust confidence
only; it never vetoes or changes BUY/SELL/HOLD.
