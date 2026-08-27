# windows-desktop — AEGIS Capture + Executor

## Components

| Artifact | Role |
|----------|------|
| `AEGIS_Capture.exe` | Draggable chart region selector, periodic capture, upload to cloud, tray, signals |
| `AEGIS_Executor.mq5` | MT5 Expert Advisor — reads cloud signals and executes trades |
| `installer/AEGIS_Setup.iss` | Inno Setup script for one-click installer |

## Quick start (dev)

```bash
cd windows-desktop/aegis_capture
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python main.py
```

## Build EXE

```bash
pip install pyinstaller
pyinstaller --noconfirm aegis_capture.spec
# output: dist/AEGIS_Capture.exe
```

## Install EA

1. Copy `mq5/AEGIS_Executor.mq5` into MT5 `MQL5/Experts/`
2. Compile in MetaEditor
3. Attach to chart; set `ApiKey`, `AccountId`, `ServerUrl`

## Capture region

1. Start AEGIS Capture
2. Drag the semi-transparent frame over the **MT5 chart only**
3. Click **Lock region** then **Start**
4. Capture continues on that screen rectangle (MT5 can stay visible in that area)

> True capture of a *minimized* window is limited by Windows; keep the chart visible in the locked region (can be a small always-on-top MT5 chart).
