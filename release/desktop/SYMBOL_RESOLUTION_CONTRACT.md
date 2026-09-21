# AEGIS canonical ↔ broker symbol resolution (contract)

**Must stay identical** in:

- `AEGIS_OHLC_Feed.mq5` (`ResolveBrokerSymbol`)
- `AEGIS_Executor.mq5` (`ResolveBrokerSymbol`)

## Algorithm (order matters)

1. Normalize to **canonical base** (strip `.r`, `m`, `#`, `.pro`, etc.) → e.g. `GBPUSD`
2. Try exact base in Market Watch (`SymbolSelect`)
3. Try known suffixes: `.r`, `m`, `.i`, `#`, `.pro`, `.raw`, `.ecn`, `.std`, `.a`, `.b`, `.c`, `i`, `.mini`, `.cfd`
4. Scan Market Watch, then all terminal symbols, match by normalized base
5. Fallback: chart `_Symbol` if base matches
6. Else fail (empty string) — **do not invent** a symbol

## Payload fields

| Field | Meaning |
|-------|---------|
| `symbol` | Canonical AEGIS registry base (`GBPUSD`) |
| `symbol_broker` | Actual MT5 symbol used for rates/orders (`GBPUSD.r`) |

When adding a new broker naming convention, update **both** EAs in the same commit.
