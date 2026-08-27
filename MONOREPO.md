# AEGIS Platform — Monorepo Guide (v1.0.0-monorepo)

## Structure

```
AEGIS_Platform_Server/
├── android-app/          # → see mobile_app/
├── mobile_app/           # Production Android
├── windows-desktop/      # Capture.exe source + EA + InnoSetup
├── macos-desktop/        # Capture for Mac
├── ios-ipad/             # Swift starter + workarounds
├── backend/              # FastAPI brain
├── shared/               # protocol.py
└── ...
```

## Same credentials everywhere

Portal → Connect mobile → **Account ID + API key** works for:

- Android
- Windows Capture
- macOS Capture
- iOS (when built)

## Downloads (website)

https://leveragefx.co/downloads

## Version tag

`v1.0.0-monorepo`
