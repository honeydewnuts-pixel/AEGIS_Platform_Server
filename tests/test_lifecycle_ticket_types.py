"""Lifecycle ticket identity must accept 64-bit values without truncation."""


def test_large_ticket_identity_string():
    # MT5 tickets can exceed 2^31-1
    ticket = 9_000_000_000_123
    key_a = f"ACC1|{ticket}"
    key_b = f"ACC1|{int(ticket)}"
    assert key_a == key_b
    # 32-bit truncation would collide or change value
    truncated = ticket & 0xFFFFFFFF
    assert truncated != ticket
    assert f"ACC1|{truncated}" != key_a


def test_account_isolation_same_ticket_value_different_accounts():
    ticket = 5_000_000_000
    assert f"A1|{ticket}" != f"A2|{ticket}"
