# Commercial plans (fintech-style)

| Plan | Devices | Trades / day | Live trading |
|------|---------|--------------|--------------|
| demo | 1 | 100 (catalog) | Analysis / demo-style (not paid live entitlement) |
| starter | 1 | 15 | Yes (commercial flag; execution safety gates separate) |
| pro | 1 | 50 | Yes |
| business | 3 | 200 | Yes |
| enterprise | 10 | Unlimited (`max_trades_per_day = 0`) | Yes |

Assign via Operator Console → **Tenants & plans** or:

`POST /api/admin/tenants/set-plan`  
`{ "account_id": "ACC-…", "plan": "business", "status": "active" }`

**Full operator procedures** (Neon SQL, curl grants without payment, Trade Copier without a separate paid product, expiry behaviour):

→ **`docs/AEGIS_OPERATOR_PLANS_AND_TRADE_COPIER_GUIDE.md`**

Device registration respects `max_devices`. Market orders respect daily trade quota (HTTP 429 when exceeded).

## Operator console tabs

Overview · Audit log · Tenants & plans · API keys · Devices · Downloads · Uploads · Alerts

## Alert channels

Email, Telegram, Slack, SMS (Twilio), **WhatsApp** (Twilio WhatsApp sandbox/number: `TWILIO_WHATSAPP_FROM`, `ALERT_WHATSAPP_TO` as `whatsapp:+E164`).
