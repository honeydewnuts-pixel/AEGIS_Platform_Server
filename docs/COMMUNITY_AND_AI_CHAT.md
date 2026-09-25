# Community + AEGIS AI (full)

Isolated from MT5 trading path.

## Features
- Rooms (general, setup, markets)
- Custom display names + online presence (90s)
- WebSocket push `/api/community/ws/{account_id}`
- Direct messages by display name
- Image attachments (JPEG/PNG/WebP/GIF ≤1.5MB)
- User reports + admin moderation (`/api/admin/chat/...`)

## Mobile 2.5.2
- Community: Name, online list, rooms, long-press report
- Tap online badge or long-press Name → open DM by peer name
- AEGIS AI support chat unchanged

## Admin
- `GET /api/admin/chat/reports?status=open`
- `POST /api/admin/chat/reports/{id}/resolve` `{status: reviewed|dismissed|actioned, note}`
- `POST /api/admin/chat/messages/{id}/delete`
