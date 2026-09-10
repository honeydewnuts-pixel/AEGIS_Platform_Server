# AEGIS Capture for Windows (V46)

Desktop client for the **AEGIS V46** cloud brain.

## What changed in V46

- **No MT5 indicator template** — capture a **plain price chart**.
- Server **pairs + rulebook registry** selects the active rulebook.
- **Risk presets** (conservative / standard / aggressive) — server calculates lot size.
- Client version `1.46.0` sent on every request.

## Setup

1. Portal account → Account ID + API key (LeverageFx portal).
2. Run `AegisCapture` (or `python main.py` with `requirements.txt`).
3. Enter Server URL (Render API), Account ID, API Key.
4. **Set chart region** over the MT5 chart window.
5. Optional: **Load registry** / **Apply risk**.
6. **START**.

## Build

See `aegis_capture.spec` + PyInstaller. Installer: `AEGIS_Setup.iss`.

```bash
pip install -r requirements.txt pyinstaller
pyinstaller aegis_capture.spec
```

## API

- `POST /aegis/analyze` — screenshot upload  
- `GET /api/registry/pairs` · `/rulebooks` · `/active`  
- `POST /api/account/risk_preset`  
- `POST /api/devices/heartbeat`
