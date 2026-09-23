# AEGIS Notification Center

Additive module. Does **not** change MT5 OHLC Feed, rule evaluation, or Executor order placement.

## Data

| Store | Role |
|-------|------|
| `signal_history` | Permanent research/audit of analysis outputs |
| `notifications` | Subscriber inbox (read/unread, delivery status) |

## APIs

- `GET /api/notifications?account_id=&limit=&unread_only=`
- `GET /api/notifications/unread-count?account_id=`
- `POST /api/notifications/{id}/read?account_id=`
- `POST /api/notifications/read-all?account_id=`
- `POST /api/notifications/{id}/acknowledge?account_id=`

Auth: same API key + `require_account_match`.

## Triggers

1. After brain/analysis records a signal → `SIGNAL_GENERATED` (HOLD only if confidence ≥ 0.70)
2. After Executor ACK (non-idempotent) → `ORDER_FILLED` / `ORDER_REJECTED`

External channels (email/Telegram/Slack/SMS/WhatsApp) use existing `AlertService` when credentials are configured. BUY/SELL with confidence ≥ 0.55 attempt external delivery by default.

## Migration

Alembic `0009_notifications` — runs on next Render deploy without touching trading tables.
