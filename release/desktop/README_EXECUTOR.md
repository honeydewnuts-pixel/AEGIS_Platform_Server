# AEGIS_Executor.mq5 v2.15 — architecture freeze for controlled VPS demo

## Partial-fill policy (explicit)

| Setting | Behaviour |
|---------|-----------|
| **PARTIAL_ACCEPT** (recommended for first demo) | First `DONE` / `DONE_PARTIAL` completes the signal. ACK reports **actual filled volume**. |
| **PARTIAL_COMPLETE_REMAINDER** | After partial, **exactly one** residual `OrderSend` with **same SL/TP**. If the residual is also partial, **stop** (no recursive remainders). ACK reports total filled. |

## Production checklist (all addressed)

- Multi-pair / chart-only modes
- Broker-symbol resolve (shared contract with Feed — see `SYMBOL_RESOLUTION_CONTRACT.md`)
- 64-bit tickets in ACK
- Position ticket discovery (never order ticket as position)
- Restart-safe `AEGIS <signal_id>` on positions/deals/orders
- ACK HTTP 2xx + independent retry queue; server idempotent by `signal_id`
- Spread vs broker retry budgets
- Adaptive filling modes
- Volume step decimals
- Partial fill policy + SL/TP on remainder

## First demo inputs

```
ExecMode = MultiPair
SymbolsList = GBPUSD,EURUSD,USDJPY
UseServerSignals = true
UseLocalFileFallback = false
OnePositionPerSymbol = true
Lots = 0.01
PollSeconds = 5
PartialFillPolicy = PARTIAL_ACCEPT
```

No further architecture changes planned until the live chain is validated:

MT5 Feed → AEGIS server → pending-batch → Executor → broker → ACK.
