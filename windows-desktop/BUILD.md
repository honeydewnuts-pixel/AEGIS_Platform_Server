# Building AEGIS_Capture.exe

## Option A — GitHub Actions (recommended)

1. Push to `main` (or run **Desktop CI** → workflow_dispatch).
2. Open the workflow run → Artifacts → **aegis-windows-desktop**.
3. Extract `AEGIS_Capture.exe`.

## Option B — Local Windows PC

```bat
cd windows-desktop\aegis_capture
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm aegis_capture.spec
dist\AEGIS_Capture.exe
```

## Option C — Inno Setup installer

After Option B:

```bat
iscc installer\AEGIS_Setup.iss
```

## Credentials

Same as mobile: Portal → Account ID + API key → paste into Capture settings.
