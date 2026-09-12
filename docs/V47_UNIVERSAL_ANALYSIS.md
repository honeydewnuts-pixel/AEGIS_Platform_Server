# V47 — Universal Analysis Runtime Integration

## Problem
Mobile uploads succeeded, but `/aegis/analyze` always ran **BrainCV V3**, which
requires visible on-chart indicators. Plain MT5 price charts (V40 design)
returned `indicators_not_detected` even for V40-eligible pairs.

## Architecture
```
Screenshot → /aegis/analyze
                ↓
         Universal Router (V40)
                ↓
    ┌───────────┴───────────┐
    eligible                rejected / unknown
    ↓                       ↓
 V40 research result     HOLD fail-closed
 (no indicator pack)     (no V3 indicators)
```

Legacy V3 remains available: form field `engine=legacy_v3`.

## Default path (mobile)
- `engine` empty → **V40 universal**
- Non-empty `symbol` only used for routing + optional OHLC when worker is up
- Worker offline → still 200 with `v40_research_awaiting_ohlc` or fail-closed state
- `production_authorized` always false on this path

## Response fields
- `analysis_path`: `v40_router` | `v40_research_ohlc` | `legacy_v3`
- `router_state`, `rulebook_ids`, `instrument`, `timeframe`
- `rule_name`: e.g. `v40_research_awaiting_ohlc`, `trading_disabled`, …
