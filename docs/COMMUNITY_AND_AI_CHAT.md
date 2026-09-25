# Community + AEGIS AI Chat

Isolated from MT5 Feed / Executor / rule engine.

## Community (operational)

### Identity
- Users choose a **display name** (3–24 chars, letter start, `[A-Za-z0-9_]`)
- Unique case-insensitive; reserved names blocked (admin, aegis, support, …)
- Auto default `Trader_XXXXXX` until set

### Presence
- `POST /api/community/presence` while Community screen is open (mobile every 5s)
- Online = `last_seen` within **90 seconds**
- `GET /api/community/online` and room list include online roster

### Rooms & messages
- Default rooms: general, setup, markets
- `GET/POST .../messages` with `after_id` for incremental poll
- Rate limit ~30 messages/minute/account
- Blocks API key / password patterns

### API summary
| Method | Path |
|--------|------|
| GET | `/api/community/rooms` |
| GET | `/api/community/rooms/{id}/messages?after_id=` |
| POST | `/api/community/rooms/{id}/messages` |
| GET | `/api/community/profile?account_id=` |
| PUT | `/api/community/profile` |
| POST | `/api/community/presence` |
| GET | `/api/community/online` |

## AEGIS AI
- `GET /api/ai/history` · `POST /api/ai/chat`
- Product support only; never places trades
