# ios-ipad — AEGIS Capture (iPhone / iPad)

## Apple restrictions

| Capability | Status | Workaround |
|------------|--------|------------|
| Background screen capture | **Not allowed** | ReplayKit: user starts capture, MT5 in foreground |
| EA auto-trade in MT5 iOS | **Not supported** | URL scheme bridge `mt5://…` + user Face ID confirm |
| Full automation | — | iPad + VNC to Windows VPS running `windows-desktop` |

## Features (parity goals)

- Login (Account ID + API key from portal)
- Dashboard / last signal
- Manual “Start Capture” (ReplayKit frame every ~3s → `/aegis/analyze`)
- Push / local notifications for BUY/SELL
- TradeBridge opens MT5 for confirmation

## Open in Xcode

Open `AEGISCapture/` in Xcode 15+, set team signing, run on device.

**Not submitted to App Store in this monorepo tag — starter only.**
