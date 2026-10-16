#!/usr/bin/env python3
"""
H1/H4 Trend + M5 Pullback hypothesis scan.
True Bid/Ask broker-correct execution. No invented fixed cost.
60/20/20 chronological. Report strict + lower-freq gates.
No post-hoc tuning. No production promotion.
"""
from __future__ import annotations
import json, time, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path("/home/workdir/artifacts/aegis_disc2")
import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.rulebooks.evaluators.common import wilder_atr14, trade_metrics

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path("/home/workdir/artifacts/discovery_hypotheses")
OUT.mkdir(parents=True, exist_ok=True)

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]

VAL_MIN_TRADES_STRICT = 350
VAL_MIN_TRADES_LF = 150
VAL_MIN_PF = 1.6
BLOCK_MIN_PF = 1.0
N_BLOCKS = 6
SLIP_ENTRY = 0.3
SLIP_EXIT = 0.3
COMM_PIPS = 0.7


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
    return df


def ema_np(x: np.ndarray, period: int) -> np.ndarray:
    a = 2.0 / (period + 1)
    o = np.empty_like(x, dtype=float)
    o[0] = x[0]
    for i in range(1, len(x)):
        o[i] = a * x[i] + (1 - a) * o[i - 1]
    return o


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    r = (
        df.set_index("datetime")
        .resample(rule, label="right", closed="right")
        .agg({"BidOpen": "first", "BidHigh": "max", "BidLow": "min", "BidClose": "last"})
        .dropna()
    )
    return r


def align_htf_to_m5(htf: pd.DataFrame, m5_dt: pd.Series, col: str) -> np.ndarray:
    s = htf[col].copy().shift(1)  # no lookahead
    aligned = s.reindex(m5_dt, method="ffill")
    return aligned.to_numpy(float)


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
        return round(float(x), nd) if np.isfinite(float(x)) else None
    except Exception:
        return None


def pip_size(sym: str) -> float:
    return 0.01 if "JPY" in sym else 0.0001


def simulate_broker(df, atr, events, side, *, stop_atr_mult, trail_atr_mult, max_hold, use_be=True):
    n = len(df)
    bo = df["BidOpen"].to_numpy(float)
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    bc = df["BidClose"].to_numpy(float)
    ao = df["AskOpen"].to_numpy(float)
    ah = df["AskHigh"].to_numpy(float)
    al = df["AskLow"].to_numpy(float)
    ac = df["AskClose"].to_numpy(float)
    trades = []
    next_allowed = 0
    for i in events:
        i = int(i)
        if i <= next_allowed or i + 1 >= n:
            continue
        A = atr[i]
        if not np.isfinite(A) or A <= 0:
            continue
        risk = float(stop_atr_mult) * float(A)
        if risk <= 0:
            continue
        if side == "LONG":
            entry = float(ao[i + 1])
            stop = entry - risk
            be = False
            end = min(n - 1, i + int(max_hold))
            exit_i = exit_px = reason = None
            for j in range(i + 1, end + 1):
                if bl[j] <= stop:
                    exit_i, exit_px, reason = j, stop, "STOP"
                    break
                rr = (bh[j] - entry) / risk
                if use_be and rr >= 1.0 and not be:
                    stop = entry
                    be = True
                if be or not use_be:
                    candidate = bc[j] - float(trail_atr_mult) * float(atr[j] if np.isfinite(atr[j]) else A)
                    if candidate > stop:
                        stop = candidate
                if j == end:
                    exit_i, exit_px, reason = j, float(bc[j]), "TIME"
            if exit_i is None:
                continue
            gross = (float(exit_px) - entry) / risk
        else:
            entry = float(bo[i + 1])
            stop = entry + risk
            be = False
            end = min(n - 1, i + int(max_hold))
            exit_i = exit_px = reason = None
            for j in range(i + 1, end + 1):
                if ah[j] >= stop:
                    exit_i, exit_px, reason = j, stop, "STOP"
                    break
                rr = (entry - al[j]) / risk
                if use_be and rr >= 1.0 and not be:
                    stop = entry
                    be = True
                if be or not use_be:
                    candidate = ac[j] + float(trail_atr_mult) * float(atr[j] if np.isfinite(atr[j]) else A)
                    if candidate < stop:
                        stop = candidate
                if j == end:
                    exit_i, exit_px, reason = j, float(ac[j]), "TIME"
            if exit_i is None:
                continue
            gross = (entry - float(exit_px)) / risk
        trades.append({"entry_i": i, "exit_i": exit_i, "entry": entry,
                       "exit": float(exit_px), "R": gross, "reason": reason, "side": side})
        next_allowed = exit_i
    return pd.DataFrame(trades)


def build_signals(df, atr_m5, sym):
    n = len(df)
    bc = df["BidClose"].to_numpy(float)
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    hours = df["hour"].to_numpy(int)

    ema20 = ema_np(bc, 20)
    ema50 = ema_np(bc, 50)
    ema200 = ema_np(bc, 200)

    h1 = resample_ohlc(df, "1h")
    h4 = resample_ohlc(df, "4h")
    for frame, period in [(h1, 50), (h1, 200), (h4, 50), (h4, 200)]:
        frame[f"EMA{period}"] = ema_np(frame["BidClose"].to_numpy(float), period)

    h1_ema50 = align_htf_to_m5(h1, df["datetime"], "EMA50")
    h1_ema200 = align_htf_to_m5(h1, df["datetime"], "EMA200")
    h1_close = align_htf_to_m5(h1, df["datetime"], "BidClose")
    h4_ema50 = align_htf_to_m5(h4, df["datetime"], "EMA50")
    h4_ema200 = align_htf_to_m5(h4, df["datetime"], "EMA200")
    h4_close = align_htf_to_m5(h4, df["datetime"], "BidClose")

    long_h1 = (h1_ema50 > h1_ema200) & (h1_close > h1_ema50)
    long_h4 = (h4_ema50 > h4_ema200) & (h4_close > h4_ema50)
    short_h1 = (h1_ema50 < h1_ema200) & (h1_close < h1_ema50)
    short_h4 = (h4_ema50 < h4_ema200) & (h4_close < h4_ema50)
    long_bias = long_h1 & long_h4
    short_bias = short_h1 & short_h4

    atr_med = pd.Series(atr_m5).rolling(100, min_periods=50).median().to_numpy()
    spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
    pip = pip_size(sym)

    long_ev, short_ev = [], []
    for i in range(250, n - 2):
        if hours[i] < 7 or hours[i] > 20:
            continue
        A = atr_m5[i]
        if not np.isfinite(A) or A <= 0:
            continue
        if not np.isfinite(atr_med[i]) or A < atr_med[i]:
            continue
        spr_pips = spread[i] / pip
        total_cost_pips = spr_pips + SLIP_ENTRY + SLIP_EXIT + COMM_PIPS
        if A < 2.0 * total_cost_pips * pip:
            continue

        if long_bias[i] and bc[i] > ema200[i]:
            touched20 = bl[i] <= ema20[i] and bc[i] > ema20[i]
            touched50 = bl[i] <= ema50[i] and bc[i] > ema50[i]
            if touched20 or touched50:
                opp = min(
                    abs(bc[i] - h1_ema50[i]) if np.isfinite(h1_ema50[i]) else 1e9,
                    abs(bc[i] - h1_ema200[i]) if np.isfinite(h1_ema200[i]) else 1e9,
                )
                if opp >= 5.0 * total_cost_pips * pip:
                    long_ev.append(i)

        if short_bias[i] and bc[i] < ema200[i]:
            touched20 = bh[i] >= ema20[i] and bc[i] < ema20[i]
            touched50 = bh[i] >= ema50[i] and bc[i] < ema50[i]
            if touched20 or touched50:
                opp = min(
                    abs(bc[i] - h1_ema50[i]) if np.isfinite(h1_ema50[i]) else 1e9,
                    abs(bc[i] - h1_ema200[i]) if np.isfinite(h1_ema200[i]) else 1e9,
                )
                if opp >= 5.0 * total_cost_pips * pip:
                    short_ev.append(i)

    return np.array(long_ev, dtype=int), np.array(short_ev, dtype=int)


def metrics_for_split(tr, t1, t2):
    if tr is None or len(tr) == 0:
        empty = {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan"), "win_rate": float("nan")}
        return empty, empty, empty, float("nan"), float("nan"), None, None
    tr_v = tr[(tr["entry_i"] >= t1) & (tr["entry_i"] < t2)]
    tr_te = tr[tr["entry_i"] >= t2]
    tr_tr = tr[tr["entry_i"] < t1]
    m_v = trade_metrics(tr_v) if len(tr_v) else {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan"), "win_rate": float("nan")}
    m_te = trade_metrics(tr_te) if len(tr_te) else {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan"), "win_rate": float("nan")}
    m_tr = trade_metrics(tr_tr) if len(tr_tr) else {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan"), "win_rate": float("nan")}
    blk_v = six_block_min_pf(tr_v) if len(tr_v) else float("nan")
    blk_te = six_block_min_pf(tr_te) if len(tr_te) else float("nan")
    avg_win = avg_los = None
    if len(tr_v):
        r = tr_v["R"].to_numpy(float)
        w, l = r[r > 0], r[r < 0]
        avg_win = float(np.mean(w)) if len(w) else None
        avg_los = float(np.mean(l)) if len(l) else None
    return m_tr, m_v, m_te, blk_v, blk_te, avg_win, avg_los


def eval_config(df, atr, long_ev, short_ev, stop_m, trail_m, hold, use_be, t1, t2, tag):
    results = []
    # BOTH
    tr_l = simulate_broker(df, atr, long_ev, "LONG", stop_atr_mult=stop_m, trail_atr_mult=trail_m, max_hold=hold, use_be=use_be)
    tr_s = simulate_broker(df, atr, short_ev, "SHORT", stop_atr_mult=stop_m, trail_atr_mult=trail_m, max_hold=hold, use_be=use_be)
    tr_all = pd.concat([tr_l, tr_s], ignore_index=True) if len(tr_l) or len(tr_s) else pd.DataFrame()
    if len(tr_all):
        tr_all = tr_all.sort_values("entry_i").reset_index(drop=True)
    m_tr, m_v, m_te, blk_v, blk_te, avg_win, avg_los = metrics_for_split(tr_all, t1, t2)
    vt = int(m_v.get("trades") or 0)
    vp = float(m_v.get("PF") or float("nan"))
    tt = int(m_te.get("trades") or 0)
    tp = float(m_te.get("PF") or float("nan"))
    max_dd = m_v.get("max_DD")
    pass_strict = (
        vt > VAL_MIN_TRADES_STRICT and np.isfinite(vp) and vp > VAL_MIN_PF
        and np.isfinite(blk_v) and blk_v > BLOCK_MIN_PF
        and np.isfinite(tp) and tp > 1.4 and tt > 200
    )
    pass_lf = (
        vt > VAL_MIN_TRADES_LF and np.isfinite(vp) and vp > VAL_MIN_PF
        and np.isfinite(blk_v) and blk_v > BLOCK_MIN_PF
        and np.isfinite(tp) and tp > 1.4 and tt > 80
    )
    results.append(dict(
        side="BOTH", config=tag, stop_atr_mult=stop_m, trail_atr_mult=trail_m,
        max_hold=hold, use_be=use_be,
        n_signals=int(len(long_ev) + len(short_ev)),
        train_trades=int(m_tr.get("trades") or 0), train_pf=rnd(m_tr.get("PF")), train_wr=rnd(m_tr.get("win_rate")),
        val_trades=vt, val_pf=rnd(vp), val_wr=rnd(m_v.get("win_rate")),
        val_avg_R=rnd(m_v.get("avg_R")), val_max_DD=rnd(max_dd),
        val_block_min_pf=rnd(blk_v), val_avg_win_R=rnd(avg_win), val_avg_los_R=rnd(avg_los),
        test_trades=tt, test_pf=rnd(tp), test_wr=rnd(m_te.get("win_rate")),
        test_avg_R=rnd(m_te.get("avg_R")), test_block_min_pf=rnd(blk_te),
        pass_strict=bool(pass_strict), pass_lf=bool(pass_lf),
    ))
    # separate sides
    for side, ev, tr in [("LONG", long_ev, tr_l), ("SHORT", short_ev, tr_s)]:
        m_tr, m_v, m_te, blk_v, _, _, _ = metrics_for_split(tr, t1, t2)
        results.append(dict(
            side=side, config=tag, stop_atr_mult=stop_m, trail_atr_mult=trail_m,
            max_hold=hold, use_be=use_be,
            n_signals=int(len(ev)),
            train_trades=int(m_tr.get("trades") or 0), train_pf=rnd(m_tr.get("PF")), train_wr=rnd(m_tr.get("win_rate")),
            val_trades=int(m_v.get("trades") or 0), val_pf=rnd(m_v.get("PF")),
            val_wr=rnd(m_v.get("win_rate")), val_avg_R=rnd(m_v.get("avg_R")),
            val_max_DD=rnd(m_v.get("max_DD")), val_block_min_pf=rnd(blk_v),
            val_avg_win_R=None, val_avg_los_R=None,
            test_trades=int(m_te.get("trades") or 0), test_pf=rnd(m_te.get("PF")),
            test_wr=rnd(m_te.get("win_rate")), test_avg_R=rnd(m_te.get("avg_R")),
            test_block_min_pf=None, pass_strict=False, pass_lf=False,
        ))
    return results


def main():
    t0 = time.time()
    all_rows = []
    strict_passers = []
    lf_candidates = []
    exit_configs = [
        ("A", 2.0, 1.0, 96, True),
        ("B", 2.5, 1.0, 144, True),
        ("C", 3.0, 1.25, 192, True),
        ("D", 2.5, 1.0, 144, False),
        ("E", 3.0, 1.25, 192, False),
    ]

    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        df = load_pair(sym)
        if df is None:
            print("  MISSING", flush=True)
            continue
        atr = wilder_atr14(df["BidHigh"].to_numpy(float), df["BidLow"].to_numpy(float), df["BidClose"].to_numpy(float))
        spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
        ms = float(np.nanmedian(spread))
        ma = float(np.nanmedian(atr[np.isfinite(atr)]))
        print(f"  rows={len(df)} med_spread={ms:.6f} med_atr={ma:.6f} spread/atr={ms/ma if ma else float('nan'):.4f}", flush=True)

        long_ev, short_ev = build_signals(df, atr, sym)
        print(f"  signals LONG={len(long_ev)} SHORT={len(short_ev)}", flush=True)
        t1, t2 = int(0.60 * len(df)), int(0.80 * len(df))
        best = None
        for tag, stop_m, trail_m, hold, use_be in exit_configs:
            rows = eval_config(df, atr, long_ev, short_ev, stop_m, trail_m, hold, use_be, t1, t2, tag)
            for row in rows:
                row["symbol"] = sym
                row["hypothesis_id"] = f"{sym}_{row['side']}_htf_pb_{tag}_s{stop_m}"
                row["family"] = "htf_trend_m5_pullback"
                row["med_spread"] = round(ms, 8)
                row["med_atr"] = round(ma, 8)
                all_rows.append(row)
                if row["side"] == "BOTH":
                    if row["pass_strict"]:
                        strict_passers.append(row)
                        print(f"  PASS-STRICT {row['hypothesis_id']} val_n={row['val_trades']} pf={row['val_pf']} blk={row['val_block_min_pf']} test_pf={row['test_pf']}", flush=True)
                    elif row["pass_lf"]:
                        lf_candidates.append(row)
                        print(f"  PASS-LF {row['hypothesis_id']} val_n={row['val_trades']} pf={row['val_pf']} blk={row['val_block_min_pf']} test_pf={row['test_pf']}", flush=True)
                    if (row["val_trades"] or 0) >= 40 and (best is None or (row["val_pf"] or 0) > (best["val_pf"] or 0)):
                        best = row
        if best:
            print(f"  best BOTH {best['hypothesis_id']} n={best['val_trades']} pf={best['val_pf']} blk={best['val_block_min_pf']} test={best['test_pf']}", flush=True)

    pd.DataFrame(all_rows).to_csv(OUT / "htf_trend_m5_pullback_results.csv", index=False)
    both = [r for r in all_rows if r["side"] == "BOTH" and (r.get("val_trades") or 0) >= 50]
    ranked = sorted(both, key=lambda x: (x.get("val_pf") or 0), reverse=True)[:15]
    summary = dict(
        hypothesis="H1/H4 trend bias + M5 EMA20/50 pullback",
        gates_strict=dict(val_min_trades=VAL_MIN_TRADES_STRICT, val_min_pf=VAL_MIN_PF, six_block_min_pf=BLOCK_MIN_PF, test_min_pf=1.4, test_min_trades=200),
        gates_lf=dict(val_min_trades=VAL_MIN_TRADES_LF, val_min_pf=VAL_MIN_PF, six_block_min_pf=BLOCK_MIN_PF, test_min_pf=1.4, test_min_trades=80),
        execution="broker_correct_bid_ask",
        cost_filter="spread+0.3+0.3+0.7 pips; reject if room <5x cost or ATR <2x cost",
        news_filter="skipped (no calendar data)",
        split="60/20/20",
        n_pairs=len(PAIRS),
        n_evals=len(all_rows),
        n_pass_strict=len(strict_passers),
        n_pass_lf=len(lf_candidates),
        strict_passers=strict_passers,
        lf_candidates=lf_candidates,
        top_by_val_pf=ranked[:10],
        elapsed_sec=round(time.time() - t0, 1),
    )
    (OUT / "htf_trend_m5_pullback_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== SUMMARY ====", flush=True)
    print(f"Evals={len(all_rows)} Pass-strict={len(strict_passers)} Pass-LF={len(lf_candidates)} elapsed={summary['elapsed_sec']}s", flush=True)
    print("Top near-misses (BOTH, val>=50) by val PF:", flush=True)
    for r in ranked[:10]:
        print(f"  {r['symbol']} {r['config']} n={r['val_trades']} pf={r['val_pf']} blk={r['val_block_min_pf']} test_n={r['test_trades']} test_pf={r['test_pf']} avgR={r['val_avg_R']}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
