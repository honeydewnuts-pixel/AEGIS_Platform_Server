# macos-desktop — AEGIS Capture (Mac)

Same cloud brain as Windows/Android. Uses Python + `mss` / Quartz for region capture.

## Permissions

System Settings → Privacy & Security → **Screen Recording** → enable Terminal / AEGIS Capture.

## Dev

```bash
cd macos-desktop/aegis_capture
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Build .app

```bash
pip install py2app
python setup.py py2app
```

`AEGIS_Executor.mq5` is identical to the Windows EA (MT5 for Mac).

## Registry (V53.6)
Server serves research-eligible pairs from `/api/registry/pairs` after deploy.
V53.6 qualified targets (production_authorized=false):
AUDUSD, EURCHF, EURGBP, GBPJPY, GBPNZD, NZDCHF, NZDJPY, NZDUSD, USDCAD, USDCHF.
Source frozen: GBPUSD V31/V35. Rejected/fail-closed: EURUSD, USDJPY, EURJPY.
