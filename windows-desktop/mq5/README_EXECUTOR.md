# AEGIS_Executor.mq5 v2.13 (production)

## Final hardening

1. **64-bit tickets** — `UlongToStr` / `long` (no `int` truncation of MT5 tickets)
2. **Restart idempotency** — `SignalAlreadyExecuted` scans positions, recent deals, orders for comment `AEGIS <signal_id>`
3. **ACK** — HTTP 2xx + retry queue; server completed-set is idempotent by `signal_id`
4. **Volume** — decimals derived from `SYMBOL_VOLUME_STEP`
5. Broker resolve, spread vs broker retries, fill modes, position ticket — retained from v2.12
