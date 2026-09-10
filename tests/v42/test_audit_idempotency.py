from app.safety.audit import AuditLedger, IdempotencyGuard

def test_audit_chain_is_tamper_evident():
    ledger = AuditLedger()
    ledger.append("ORDER_ACCEPTED", "x1", {"mode": "PAPER"})
    ledger.append("ORDER_REJECTED", "x2", {"reason": "STALE_DATA"})
    assert ledger.verify_chain()
    assert len(ledger.events) == 2

def test_idempotency_blocks_duplicate_client_order_id():
    guard = IdempotencyGuard()
    assert guard.accept("x1") is True
    assert guard.accept("x1") is False
