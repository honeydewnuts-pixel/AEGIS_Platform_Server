# AEGIS Capture — macOS

Region capture for MetaTrader 5 on Mac. Sends frames to the AEGIS cloud brain.

## Features
- Screen region capture (requires **Screen Recording** permission)
- Multipart upload to `/aegis/analyze` (same as mobile/Windows)
- **MT5 Color Match Guide** in-app
- `AEGIS_Executor.mq5` for Mac MT5

## Build (macOS only)

```bash
chmod +x build.sh
./build.sh
```

Output: `AEGIS_Capture_v1.0.0.dmg`

## Client setup
1. Open DMG → drag app to Applications
2. System Settings → Privacy → Screen Recording → enable AEGIS Capture
3. Enter portal API key + account id
4. Open **Color Guide** and match MT5 indicators
5. Start capture with MT5 chart visible
