# V53.6 Cost Model & Risk Tolerance Remediation

## Cost model

| Mode | Use | Deduction |
|------|-----|-----------|
| `legacy_fixed_r` | Historical V31/V35 / V53.6 metric **reproduction** only | Fixed **0.085R** per trade |
| `bid_ask_only` | Operational cash tests, demo, live analysis of R | **0** extra R; spread via Ask entry / Bid exit |
| `configured` | Explicit commission_r / fixed_cost_r when known | Configured only; never invent |

- Entry: next-bar **AskOpen**
- Stop trigger (short): **BidHigh**
- Time exit: **BidClose**
- Do **not** subtract spread again when Bid/Ask already used.

Legacy evaluator path: `simulate_short(..., cost_mode="legacy_fixed_r")` (default) or `simulate_short_legacy`.

Operational path: `simulate_short_operational` / `cost_mode="bid_ask_only"`.

Config helper: `app.services.execution_cost_model.cost_config_for(instrument, account_type)`.

## Risk tolerance

Stored on subscription (`risk_tolerance_pct`). Budget = equity × pct / 100.

`PortfolioRiskService.size_order`:

- Requires equity (reject `equity_required_for_risk_sizing`).
- Rejects when min lot would exceed remaining budget (`min_lot_exceeds_risk_budget`).
- Does **not** silently force min lot above risk.

Autonomous OHLC path calls `size_order` before `ExecutorSignalService.publish`.

## Modes

| Mode | Cost | Risk |
|------|------|------|
| Historical reproduction | legacy 0.085R | N/A (R-space metrics) |
| Historical operational | bid_ask_only | Optional cash sizing separate from qualification |
| Demo | Broker fills; no 0.085R | Enforced size_order |
| Live | Broker fills; auth required | Enforced; production_authorization still false by default |
