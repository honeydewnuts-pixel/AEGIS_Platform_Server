# V44 Decision Contract

Required fields:
- correlation_id
- decision_timestamp
- instrument
- timeframe
- data_timestamp
- rulebook_id
- neural_model_id (nullable)
- rulebook_state
- neural_state
- neural_confidence (nullable)
- decision_side
- execution_mode
- authorization
- risk_gate
- safety_gate
- final_action
- rejection_reason

The contract is append-only/auditable. Repeated correlation_id values must be idempotent. Unknown model or rulebook IDs fail closed.
