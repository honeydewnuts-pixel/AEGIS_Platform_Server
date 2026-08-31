# AEGIS Capture — Windows

Draggable chart-region capture for MetaTrader 5. Sends PNGs to the AEGIS cloud brain and shows BUY/SELL/HOLD.

## Features
- Draggable **chart region** (not full desktop)
- Same API as mobile (`POST /aegis/analyze`, field `image`)
- **MT5 Color Match Guide** (in-app button + installed assets)
- Writes `aegis_signal.txt` for `mq5/AEGIS_Executor.mq5`
- Start / Stop, interval, credentials

## Build (Windows 10+)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller aegis_capture.spec
```

Produces `dist\AEGIS_Capture.exe`.

### Installer (Inno Setup 6)

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
2. Open `AEGIS_Setup.iss` → **Compile**
3. Output: `Output\AEGIS_Capture_Setup.exe`

## Client setup
1. Install via `AEGIS_Capture_Setup.exe`
2. Enter Server URL, Account ID, API key (from leveragefx.co portal)
3. **COLOR GUIDE** — match MT5 indicators exactly
4. **SELECT CHART REGION** — lock over MT5 chart
5. **START**
6. Optional: copy `mq5\AEGIS_Executor.mq5` into MetaEditor → compile → attach to chart

## Note
MT5 chart must stay **visible** under the locked region (Windows cannot capture fully minimized windows reliably).
