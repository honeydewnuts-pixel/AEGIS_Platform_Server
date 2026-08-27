# shared/

Common protocol definitions for every AEGIS client platform.

- `protocol.py` — JSON envelope + path constants
- Clients may re-implement the same schema in Kotlin / Swift / MQL5

**Envelope**

```json
{
  "device_id": "string",
  "account_id": "string",
  "platform": "android|windows|macos|ios",
  "type": "screenshot|trade_signal|heartbeat|auth",
  "api_key": "string",
  "ts": 1710000000.0,
  "payload": {}
}
```
