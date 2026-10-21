#!/usr/bin/env python3
"""Frozen v2.1 signal research — no parameter optimization, no cash PF."""
from __future__ import annotations
import json, hashlib, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from indicators_v21 import compute_stack_v21
from signal_engine_v21 import generate_events, target_state_machine

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
PAIRS = ["AUDUSD","EURCHF","EURGBP","EURJPY","EURUSD","GBPJPY","GBPNZD","GBPUSD","NZDCHF","NZDJPY","USDCAD","USDCHF","USDJPY"]

def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return df, h

def run_sym(sym):
    df, h = load(sym)
    c = df["bid_close"].astype(float).to_numpy()
    hi = df["bid_high"].astype(float).to_numpy()
    lo = df["bid_low"].astype(float).to_numpy()
    ind = compute_stack_v21(c, hi, lo)
    events = generate_events(ind)
    elig = [e for e in events if e["eligible"]]
    tgt, changes, conflicts = target_state_machine(events, len(c))
    bear = sum(1 for e in elig if e["action"] == "EARLY_BEARISH_REVERSAL")
    bull = sum(1 for e in elig if e["action"] == "EARLY_BULLISH_REVERSAL")
    # year counts
    years = {}
    for e in elig:
        y = str(df.loc[e["confirm_idx"], "datetime"].year)
        years[y] = years.get(y, 0) + 1
    return dict(
        symbol=sym, sha256=h, rows=len(df),
        n_raw_events=len(events), n_eligible=len(elig),
        n_early_bear=bear, n_early_bull=bull,
        n_target_changes=len(changes), n_conflicts=conflicts,
        year_counts=years,
        rbb_source="SMA7_of_RSI9", ddof=0,
    ), elig, df

def main():
    rows = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        s, elig, df = run_sym(sym)
        rows.append(s)
        print(f"  elig={s['n_eligible']} bear={s['n_early_bear']} bull={s['n_early_bull']} changes={s['n_target_changes']} conflicts={s['n_conflicts']}", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "instrument_signal_summary.csv", index=False)
    # manifest
    man = [{k: r[k] for k in ("symbol","sha256","rows")} for r in rows]
    pd.DataFrame(man).to_csv(OUT / "dataset_manifest.csv", index=False)
    summary = dict(
        research_id="BB17_BB34_RSI_SWING_V2.1",
        production_authorized=False, execution_authorized=False,
        rbb_source="SMA7_of_RSI9", ddof=0,
        total_eligible=sum(r["n_eligible"] for r in rows),
        total_bear=sum(r["n_early_bear"] for r in rows),
        total_bull=sum(r["n_early_bull"] for r in rows),
        total_target_changes=sum(r["n_target_changes"] for r in rows),
        total_conflicts=sum(r["n_conflicts"] for r in rows),
        instruments=rows,
        note="Signal engine only; no trade management; no PF",
    )
    (OUT / "v21_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("TOTAL eligible", summary["total_eligible"], "DONE", flush=True)

if __name__ == "__main__":
    main()
