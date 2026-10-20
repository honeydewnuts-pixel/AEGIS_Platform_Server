#!/usr/bin/env python3
"""AEGIS_DBT_RSI_REVERSAL_V1 — signal/event research (not full profitability)."""
from __future__ import annotations
import json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from indicators import compute_stack
from state_engine import evolve_states, early_rsi_reversal_events, SWING_LEFT, SWING_RIGHT

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]


def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    # Use bid OHLC for indicator path (descriptive); keep ask for spread
    close = df["bid_close"].astype(float).to_numpy()
    high = df["bid_high"].astype(float).to_numpy()
    low = df["bid_low"].astype(float).to_numpy()
    spread = (df["ask_close"] - df["bid_close"]).astype(float).to_numpy()
    return df, close, high, low, spread


def analyze(sym):
    df, close, high, low, spread = load(sym)
    ind = compute_stack(close, high, low)
    states = evolve_states(ind)
    events = early_rsi_reversal_events(ind, states)
    elig = [e for e in events if e["eligible"]]
    rej = [e for e in events if not e["eligible"]]
    bear = [e for e in elig if e["kind"] == "EARLY_BEARISH_REVERSAL"]
    bull = [e for e in elig if e["kind"] == "EARLY_BULLISH_REVERSAL"]
    # state distribution
    from collections import Counter
    sc = Counter(states.tolist())
    # WPR vs RBB_U frequency (cross-scale diagnostic)
    wpr = ind["WPR60"]
    rbb_u = ind["RBB_U"]
    mask = ~np.isnan(wpr) & ~np.isnan(rbb_u)
    wpr_above = int(np.sum(wpr[mask] > rbb_u[mask])) if mask.any() else 0
    wpr_n = int(mask.sum())
    return dict(
        symbol=sym, rows=len(df),
        n_events_total=len(events), n_eligible=len(elig), n_rejected=len(rej),
        n_early_bearish=len(bear), n_early_bullish=len(bull),
        state_counts={k: int(v) for k, v in sc.items()},
        wpr_gt_rbb_u_count=wpr_above, wpr_obs=wpr_n,
        wpr_gt_rbb_u_rate=(wpr_above / wpr_n if wpr_n else None),
        swing_L=SWING_LEFT, swing_R=SWING_RIGHT,
        provisional_swing=True,
        med_spread=float(np.nanmedian(spread)),
    ), events, states, df


def main():
    t0 = time.time()
    summaries = []
    all_events = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        s, events, states, df = analyze(sym)
        summaries.append(s)
        print(
            f"  events={s['n_events_total']} eligible={s['n_eligible']} "
            f"bear={s['n_early_bearish']} bull={s['n_early_bullish']} "
            f"wpr>rbb_u rate={s['wpr_gt_rbb_u_rate']}",
            flush=True,
        )
        for e in events:
            if e["eligible"]:
                row = dict(symbol=sym, **{k: v for k, v in e.items() if k != "rsi_ma7"})
                row["ts_extreme"] = str(df.loc[e["extreme_idx"], "datetime"])
                row["ts_confirm"] = str(df.loc[e["confirm_idx"], "datetime"])
                all_events.append(row)

    pd.DataFrame(summaries).to_csv(OUT / "instrument_signal_summary.csv", index=False)
    pd.DataFrame(all_events).to_csv(OUT / "early_rsi_event_ledger.csv", index=False)
    summary = dict(
        research_id="AEGIS_DBT_RSI_REVERSAL_V1",
        production_authorized=False,
        execution_authorized=False,
        provisional_swing={"L": SWING_LEFT, "R": SWING_RIGHT},
        n_pairs=len(PAIRS),
        total_eligible=sum(s["n_eligible"] for s in summaries),
        total_bear=sum(s["n_early_bearish"] for s in summaries),
        total_bull=sum(s["n_early_bullish"] for s in summaries),
        instruments=summaries,
        elapsed_sec=round(time.time() - t0, 1),
        note="Signal/event research only; swing definition PROVISIONAL; no trade management / no PF claim",
    )
    (OUT / "dbt_rsi_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== SUMMARY ====", flush=True)
    print(f"eligible early RSI events: {summary['total_eligible']} (bear={summary['total_bear']} bull={summary['total_bull']})", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
