# Brain version consumed by all clients

| Item | Value |
|------|--------|
| Active rulebook | **v3** |
| Active indicator stack | **v3** (5 indicators) |
| Primary neural | **AEGIS_NEURAL_V3** |
| Fallback neural | **AEGIS_NEURAL_V2** (automatic on v3 failure) |

Clients (Android APK, Windows Capture, macOS Capture) all call the same cloud endpoints.
No client-side model swap is required — fallback is server-side and seamless.
