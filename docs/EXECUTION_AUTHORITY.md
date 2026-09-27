# Execution authority (anti mobile-select trades)

## Rule
**Mobile pair selection and screenshot analysis do not place trades.**

| Path | May publish to Executor / place order? |
|------|----------------------------------------|
| `POST /aegis/analyze` (mobile screenshot) | **No** (default). Analysis + notifications only. |
| OHLC Feed `CLOSED` bar → `AutonomousOhlcSignalService` | **Yes** — V31 SHORT / V53.6 entry conditions |
| Executor pending-batch | Executes only server-published pending signals |

## Config (Render)
```
SCREENSHOT_PUBLISHES_TO_EXECUTOR=false
SCREENSHOT_TRIGGERS_WORKER_EXECUTION=false
```
Do not set these to true for production or controlled V53.6 demos.

## Risk budget
`risk_budget = equity × tolerance%`
`max_pairs = min(24, floor(budget / symbol_min_notional))`
Each new pair takes an equal share of **remaining** budget (`slot_budget`).
Lot size scales from slot budget; never from mobile UI alone.
