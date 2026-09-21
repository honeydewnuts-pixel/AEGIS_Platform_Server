# AEGIS_Executor.mq5 v2.14 (production)

## Partial-fill policy (explicit)

| Mode | Behaviour |
|------|-----------|
| **PARTIAL_ACCEPT** (default) | Any fill (full or partial) completes the signal. ACK reports **actual filled volume**. |
| **PARTIAL_COMPLETE_REMAINDER** | After partial, one residual OrderSend for remaining volume; ACK reports total filled. |

## Other production items

- ResolveBrokerSymbol aligned with Feed v2.02
- Exact comment match: `AEGIS <signal_id>` only
- Position ticket = real position or 0 (never order ticket masquerading)
- 64-bit tickets, ACK HTTP verify + retry, restart idempotency
