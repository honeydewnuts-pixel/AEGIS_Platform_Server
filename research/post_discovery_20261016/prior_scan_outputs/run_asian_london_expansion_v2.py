#!/usr/bin/env python3
"""
Asian-range → London expansion v2 (structural, cost-aware).

Fixes from v1:
  - M5 ATR is too small relative to a 7-hour Asian range (~6–12× M5 ATR).
  - Use H1 ATR proxy and/or percentile compression of historical Asian ranges.

Economic hypothesis:
  Compressed Asian range (00:00–07:00 UTC) → break at London open → multi-hour
  directional expansion. Expected structural move >> spread.

Gates reported against both strict (val>350) and lower-freq (val>150).
Execution: broker_correct Bid/Ask. Split 60/20/20. No promotion.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/home/workdir/artifacts/aegis_disc2")
import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.rulebooks.evaluators.common import (
    wilder_atr14,
    trade_metrics,
    simulate_short_broker_correct,
    simulate_long_broker_correct,
)

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path("/home/workdir/artifacts/discovery_hypotheses")
OUT.mkdir(parents=True, exist_ok=True)

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
VAL_MIN_TRADES_STRICT = 350
VAL_MIN_TRADES_LF = 150
VAL_MIN_PF = 1.6
BLOCK_MIN_PF = 1.0
N_BLOCKS = 6


def load_pair(sym: str) -> pd.DataFrame | None:
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    if not p.is_file():
        return None
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    for std, src in [
        ("BidOpen", "bid_open"), ("BidHigh", "bid_high"),
        ("BidLow", "bid_low"), ("BidClose", "bid_close"),
        ("AskOpen", "ask_open"), ("AskHigh", "ask_high"),
        ("AskLow", "ask_low"), ("AskClose", "ask_close"),
    ]:
        df[std] = df[src].astype(float)
    df["hour"] = df["datetime"].dt.hour
    df["date"] = df["datetime"].dt.date
    return df


def h1_atr_proxy(df: pd.DataFrame) -> np.ndarray:
    h1 = (
        df.set_index("datetime")
        .resample("1h")
        .agg({"BidOpen": "first", "BidHigh": "max", "BidLow": "min", "BidClose": "last"})
        .dropna()
    )
    atr_h1 = wilder_atr14(
        h1["BidHigh"].to_numpy(float),
        h1["BidLow"].to_numpy(float),
        h1["BidClose"].to_numpy(float),
    )
    atr_s = pd.Series(atr_h1, index=h1.index)
    atr_m5 = atr_s.reindex(df["datetime"]).ffill().bfill().to_numpy(float)
    return atr_m5


def six_block_min_pf(trades: pd.DataFrame) -> float:
    if trades is None or len(trades) < N_BLOCKS:
        return float("nan")
    r = trades["R"].to_numpy(float)
    n = len(r)
    edges = [int(round(i * n / N_BLOCKS)) for i in range(N_BLOCKS + 1)]
    pfs = []
    for b in range(N_BLOCKS):
        seg = r[edges[b]:edges[b + 1]]
        if len(seg) == 0:
            pfs.append(float("nan"))
            continue
        gp = float(seg[seg > 0].sum())
        gl = float(-seg[seg < 0].sum())
        pfs.append(gp / gl if gl > 0 else float("nan"))
    return float(np.nanmin(pfs)) if pfs else float("nan")


def rnd(x, nd=4):
    try:
        return round(float(x), nd) if np.isfinite(x) else None
    except Exception:
        return None


def build_asian_sessions(df: pd.DataFrame, atr_h1: np.ndarray, london_hour: int = 7):
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    hours = df["hour"].to_numpy(int)
    dates = df["date"].to_numpy()
    unique_dates = pd.unique(dates)
    date_to_idxs = {}
    for i, d in enumerate(dates):
        date_to_idxs.setdefault(d, []).append(i)

    sessions = []
    for d in unique_dates:
        idxs = date_to_idxs[d]
        asian_idxs = [i for i in idxs if 0 <= hours[i] < london_hour]
        london_idxs = [i for i in idxs if hours[i] >= london_hour]
        if len(asian_idxs) < 12 or len(london_idxs) < 6:
            continue
        a_hi = float(np.max(bh[asian_idxs]))
        a_lo = float(np.min(bl[asian_idxs]))
        width = a_hi - a_lo
        last_asian = asian_idxs[-1]
        A = atr_h1[last_asian]
        if not np.isfinite(A) or A <= 0:
            continue
        sessions.append(dict(
            date=d, asian_idxs=asian_idxs, london_idxs=london_idxs,
            a_hi=a_hi, a_lo=a_lo, width=width, atr_h1=A,
            width_atr=width / A, last_asian=last_asian,
        ))
    return sessions


def events_from_sessions(sessions, df, *, max_width_atr=None, max_percentile=None,
                         max_width_pips=None, pip_size=0.0001, confirm_bars=1):
    widths = np.array([s["width"] for s in sessions], dtype=float)
    long_ev, short_ev = [], []
    bc = df["BidClose"].to_numpy(float)
    n = len(df)

    if max_percentile is not None and len(widths) > 20:
        thresh = float(np.percentile(widths, max_percentile * 100))
    else:
        thresh = None

    for s in sessions:
        compressed = True
        if max_width_atr is not None and s["width_atr"] > max_width_atr:
            compressed = False
        if max_width_pips is not None and s["width"] > max_width_pips * pip_size:
            compressed = False
        if thresh is not None and s["width"] > thresh:
            compressed = False
        if not compressed:
            continue
        if s["width"] < 3.0 * pip_size:
            continue

        a_hi, a_lo = s["a_hi"], s["a_lo"]
        broken_l = broken_s = False
        for j in s["london_idxs"]:
            if broken_l and broken_s:
                break
            if not broken_l and bc[j] > a_hi:
                ok = True
                if confirm_bars > 1:
                    for k in range(1, confirm_bars):
                        if j + k >= n or bc[j + k] <= a_hi:
                            ok = False
                            break
                if ok:
                    long_ev.append(j)
                    broken_l = True
            if not broken_s and bc[j] < a_lo:
                ok = True
                if confirm_bars > 1:
                    for k in range(1, confirm_bars):
                        if j + k >= n or bc[j + k] >= a_lo:
                            ok = False
                            break
                if ok:
                    short_ev.append(j)
                    broken_s = True
    return np.array(long_ev, dtype=int), np.array(short_ev, dtype=int)


def eval_side(df, atr_m5, events, side, stop_m, trail_m, max_hold, t1, t2):
    sim = simulate_short_broker_correct if side == "SHORT" else simulate_long_broker_correct
    val_ev = events[(events >= t1) & (events < t2)]
    test_ev = events[events >= t2]
    train_ev = events[events < t1]

    def run(e):
        if len(e) == 0:
            return None, {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan")}
        tr = sim(df, atr_m5, e, stop_atr_mult=stop_m, trail_atr_mult=trail_m, max_hold=max_hold)
        return tr, trade_metrics(tr)

    tr_v, m_v = run(val_ev)
    _, m_te = run(test_ev)
    _, m_tr = run(train_ev)
    blk = six_block_min_pf(tr_v) if tr_v is not None and len(tr_v) else float("nan")
    vt = int(m_v.get("trades") or 0)
    vp = float(m_v.get("PF") or float("nan"))

    pass_strict = vt > VAL_MIN_TRADES_STRICT and np.isfinite(vp) and vp > VAL_MIN_PF and np.isfinite(blk) and blk > BLOCK_MIN_PF
    pass_lf = vt > VAL_MIN_TRADES_LF and np.isfinite(vp) and vp > VAL_MIN_PF and np.isfinite(blk) and blk > BLOCK_MIN_PF

    avg_winner_R = None
    if tr_v is not None and len(tr_v):
        r = tr_v["R"].to_numpy(float)
        wins = r[r > 0]
        if len(wins):
            avg_winner_R = float(np.mean(wins))

    return dict(
        side=side, stop_atr_mult=stop_m, trail_atr_mult=trail_m, max_hold=max_hold,
        n_signals_all=int(len(events)),
        train_trades=int(m_tr.get("trades") or 0), train_pf=rnd(m_tr.get("PF")),
        val_trades=vt, val_pf=rnd(vp), val_avg_R=rnd(m_v.get("avg_R")),
        val_max_DD=rnd(m_v.get("max_DD")), val_block_min_pf=rnd(blk),
        val_avg_winner_R=rnd(avg_winner_R),
        test_trades=int(m_te.get("trades") or 0), test_pf=rnd(m_te.get("PF")),
        test_avg_R=rnd(m_te.get("avg_R")),
        pass_strict=bool(pass_strict), pass_lf=bool(pass_lf),
    )


def main():
    t0 = time.time()
    rows = []
    winners_strict, winners_lf = [], []

    compressions = [
        (1.0, None, None, "h1atr1.0"),
        (1.2, None, None, "h1atr1.2"),
        (1.5, None, None, "h1atr1.5"),
        (None, 0.30, None, "pct30"),
        (None, 0.40, None, "pct40"),
        (None, None, 25.0, "pips25"),
        (None, None, 35.0, "pips35"),
        (None, None, 45.0, "pips45"),
    ]
    risk_grid = [
        (2.5, 1.0,  96, 1),
        (3.0, 1.25, 120, 1),
        (3.5, 1.5,  144, 1),
        (2.5, 1.0,  120, 2),
        (3.0, 1.0,   72, 1),
    ]

    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        df = load_pair(sym)
        if df is None:
            print("  MISSING", flush=True)
            continue
        atr_m5 = wilder_atr14(
            df["BidHigh"].to_numpy(float),
            df["BidLow"].to_numpy(float),
            df["BidClose"].to_numpy(float),
        )
        atr_h1 = h1_atr_proxy(df)
        spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
        ms = float(np.nanmedian(spread))
        ma = float(np.nanmedian(atr_m5[np.isfinite(atr_m5)]))
        ratio = (ms / ma) if ma else float("nan")
        print(f"  rows={len(df)} med_spread={ms:.6f} med_atr_m5={ma:.6f} spread/atr={ratio:.4f}", flush=True)

        sessions = build_asian_sessions(df, atr_h1, london_hour=7)
        print(f"  valid Asian sessions={len(sessions)}", flush=True)
        if sessions:
            wa = [s["width_atr"] for s in sessions]
            print(f"  width/H1ATR p25/p50/p75={np.percentile(wa,[25,50,75])}", flush=True)

        pip = 0.01 if "JPY" in sym else 0.0001
        t1, t2 = int(0.60 * len(df)), int(0.80 * len(df))
        best = None

        for max_wa, max_pct, max_pips, comp_tag in compressions:
            pips_arg = max_pips
            if max_pips is not None and "JPY" in sym:
                pips_arg = max_pips  # already in "pips"; price units handled by pip_size
            for stop_m, trail_m, hold, conf in risk_grid:
                long_ev, short_ev = events_from_sessions(
                    sessions, df,
                    max_width_atr=max_wa,
                    max_percentile=max_pct,
                    max_width_pips=pips_arg,
                    pip_size=pip,
                    confirm_bars=conf,
                )
                for side, ev in [("LONG", long_ev), ("SHORT", short_ev)]:
                    if len(ev) < 20:
                        continue
                    row = eval_side(df, atr_m5, ev, side, stop_m, trail_m, hold, t1, t2)
                    row["symbol"] = sym
                    row["hypothesis_id"] = f"{side}_asianL_{comp_tag}_s{stop_m}_t{trail_m}_h{hold}_c{conf}"
                    row["family"] = "asian_london_expansion"
                    row["compression"] = comp_tag
                    row["confirm_bars"] = conf
                    row["med_spread"] = round(ms, 8)
                    row["med_atr"] = round(ma, 8)
                    rows.append(row)

                    if row["pass_strict"]:
                        winners_strict.append(row)
                        print(f"  PASS-STRICT {row['hypothesis_id']} n={row['val_trades']} pf={row['val_pf']} blk={row['val_block_min_pf']}", flush=True)
                    elif row["pass_lf"]:
                        winners_lf.append(row)
                        print(f"  PASS-LF     {row['hypothesis_id']} n={row['val_trades']} pf={row['val_pf']} blk={row['val_block_min_pf']}", flush=True)

                    if (row["val_trades"] or 0) >= 30 and (
                        best is None or (row["val_pf"] or 0) > (best["val_pf"] or 0)
                    ):
                        best = row

        if best:
            print(
                f"  best {best['hypothesis_id']} n={best['val_trades']} "
                f"pf={best['val_pf']} blk={best['val_block_min_pf']} "
                f"strict={best['pass_strict']} lf={best['pass_lf']}",
                flush=True,
            )

    pd.DataFrame(rows).to_csv(OUT / "asian_london_v2_results.csv", index=False)
    summary = dict(
        hypothesis="Asian-range → London expansion v2 (H1-ATR / percentile / pips compression)",
        gates_strict=dict(val_min_trades=VAL_MIN_TRADES_STRICT, val_min_pf=VAL_MIN_PF, six_block_min_pf=BLOCK_MIN_PF),
        gates_lf=dict(val_min_trades=VAL_MIN_TRADES_LF, val_min_pf=VAL_MIN_PF, six_block_min_pf=BLOCK_MIN_PF),
        execution="broker_correct_bid_ask",
        split="60/20/20",
        n_pairs=len(PAIRS),
        n_evals=len(rows),
        n_pass_strict=len(winners_strict),
        n_pass_lf=len(winners_lf),
        winners_strict=winners_strict,
        winners_lf=winners_lf,
        elapsed_sec=round(time.time() - t0, 1),
    )
    (OUT / "asian_london_v2_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n==== SUMMARY ====", flush=True)
    print(f"Evals={len(rows)}  Pass-strict={len(winners_strict)}  Pass-LF={len(winners_lf)}  elapsed={summary['elapsed_sec']}s", flush=True)
    if winners_strict:
        print("STRICT WINNERS:", flush=True)
        for w in winners_strict:
            print(f"  {w['symbol']} {w['hypothesis_id']} val_n={w['val_trades']} pf={w['val_pf']} blk={w['val_block_min_pf']} test_pf={w['test_pf']}", flush=True)
    if winners_lf:
        print("LF WINNERS (val>150):", flush=True)
        for w in winners_lf:
            print(f"  {w['symbol']} {w['hypothesis_id']} val_n={w['val_trades']} pf={w['val_pf']} blk={w['val_block_min_pf']} test_pf={w['test_pf']}", flush=True)

    ranked = sorted(
        [r for r in rows if (r.get("val_trades") or 0) >= 50 and r.get("val_pf")],
        key=lambda x: (x["val_pf"] or 0),
        reverse=True,
    )[:20]
    print("Top near-misses (val_trades>=50):", flush=True)
    for r in ranked:
        print(
            f"  {r['symbol']} {r['hypothesis_id']} n={r['val_trades']} "
            f"pf={r['val_pf']} blk={r['val_block_min_pf']} test={r['test_pf']} "
            f"avgR={r['val_avg_R']} avgWinR={r.get('val_avg_winner_R')}",
            flush=True,
        )
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
