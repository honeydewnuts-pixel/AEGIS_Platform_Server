from __future__ import annotations
import hashlib
from pathlib import Path
import pandas as pd

def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def audit_dataset(path: str | Path, expected_minutes: int = 5) -> dict:
    p = Path(path)
    out = {'file': p.name, 'size_bytes': p.stat().st_size, 'sha256': sha256_file(p)}
    try:
        df = pd.read_csv(p)
        dt = pd.to_datetime(df['datetime'], errors='coerce') if 'datetime' in df else pd.Series(dtype='datetime64[ns]')
        out.update({
            'rows': len(df), 'columns': '|'.join(df.columns),
            'date_start': str(dt.min()) if len(dt) else '', 'date_end': str(dt.max()) if len(dt) else '',
            'duplicate_timestamps': int(dt.duplicated(keep=False).sum()) if len(dt) else 0,
            'backward_jumps': int((dt.diff().dt.total_seconds() < 0).sum()) if len(dt) else 0,
            'ohlc_available': all(c in df.columns for c in ('BidOpen','BidHigh','BidLow','BidClose')),
            'bid_ask_available': all(c in df.columns for c in ('BidOpen','BidHigh','BidLow','BidClose','AskOpen','AskHigh','AskLow','AskClose')),
            'spread_available': all(c in df.columns for c in ('AskOpen','AskHigh','AskLow','AskClose')),
            'status': 'AUDITABLE'
        })
    except Exception as e:
        out.update({'rows':0,'columns':'','status':f'DATA_INVALID:{type(e).__name__}:{e}'})
    return out
