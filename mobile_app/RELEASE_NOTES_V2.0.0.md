# AEGIS Mobile v2.0.0

Fresh mobile capture/upload baseline.

## Primary regression fixes

- Screenshot upload no longer depends on MT5 worker connectivity.
- MT5 symbol is attached only when `/api/trading/health` confirms a connected worker.
- Permanent 4xx upload failures are not endlessly retried or queued.
- Transient failures retain controlled retry/offline behavior.
- Every capture uses a unique temporary file.
- Uploads are serialized to prevent concurrent capture/file races.
- Release logging is reduced to BASIC so screenshot multipart bodies are not logged.
- Existing V40 registry, PAIRS/RULES, MT5 connection, risk, HUD, accessibility,
  battery and diagnostics functionality is retained.

## Version

- versionCode: 23
- versionName: 2.0.0
