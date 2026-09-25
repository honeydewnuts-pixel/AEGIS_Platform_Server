# Community + AEGIS AI Chat

Isolated from MT5 Feed / Executor / rule engine.

## Community
- `GET /api/community/rooms`
- `GET /api/community/rooms/{room_id}/messages`
- `POST /api/community/rooms/{room_id}/messages` `{ account_id, body }`

Default rooms: general, setup, markets.

## AEGIS AI
- `GET /api/ai/history?account_id=`
- `POST /api/ai/chat` `{ account_id, message }`

AI is product-support only. Never places trades.

Display names are anonymized (`Trader-XXXXXX`). Do not post API keys in community.
