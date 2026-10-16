#!/usr/bin/env python3
"""Cost-aware Bid/Ask hypothesis scan. Gates: 60/20/20, val trades>350, PF>1.6, 6-block min>1."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/home/workdir/artifacts/aegis_disc2")
sys.path.insert(0, str(ROOT / "backend"))
from app.rulebooks.evaluators.common import (
    wilder_atr14, trade_metrics,
    simulate_short_broker_correct, simulate_long_broker_correct,
)

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path("/home/workdir/artifacts/discovery_hypotheses")
OUT.mkdir(parents=True, exist_ok=True)
PAIRS = [
    "AUDUSD","EURCHF","EURGBP","EURJPY","EURUSD","GBPJPY",
    "GBPNZD","GBPUSD","NZDCHF","NZDJPY","USDCAD","USDCHF","USDJPY",
]
VAL_MIN_TRADES, VAL_MIN_PF, BLOCK_MIN_PF, N_BLOCKS = 350, 1.6, 1.0, 6


def load_pair(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    if not p.is_file():
        return None
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    for std, src in [
        ("BidOpen","bid_open"),("BidHigh","bid_high"),("BidLow","bid_low"),("BidClose","bid_close"),
        ("AskOpen","ask_open"),("AskHigh","ask_high"),("AskLow","ask_low"),("AskClose","ask_close"),
    ]:
        df[std] = df[src].astype(float)
    return df


def ema(x, p):
    a = 2/(p+1); o = np.empty_like(x, float); o[0] = x[0]
    for i in range(1, len(x)):
        o[i] = a*x[i] + (1-a)*o[i-1]
    return o


def rsi(c, p):
    d = np.diff(c, prepend=c[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    n = len(c); au = np.zeros(n); ad = np.zeros(n); out = np.full(n, np.nan)
    if n <= p: return out
    au[p] = up[1:p+1].mean(); ad[p] = dn[1:p+1].mean()
    for i in range(p+1, n):
        au[i] = (au[i-1]*(p-1)+up[i])/p; ad[i] = (ad[i-1]*(p-1)+dn[i])/p
    rs = np.divide(au, ad, out=np.zeros(n), where=ad > 1e-12)
    out = 100 - 100/(1+rs); out[:p] = np.nan
    return out


def throttle(idx, gap=12):
    if len(idx) == 0: return idx.astype(int)
    out = [int(idx[0])]
    for i in idx[1:]:
        if int(i) - out[-1] >= gap: out.append(int(i))
    return np.array(out, int)


def six_block_min_pf(trades):
    if trades is None or len(trades) < N_BLOCKS: return float("nan")
    r = trades["R"].to_numpy(float); n = len(r)
    edges = [int(round(i * n / N_BLOCKS)) for i in range(N_BLOCKS + 1)]
    mins = []
    for b in range(N_BLOCKS):
        chunk = r[edges[b]:edges[b+1]]
        if len(chunk) == 0: return float("nan")
        gp = float(chunk[chunk > 0].sum()); gl = float((-chunk[chunk < 0]).sum())
        pf = gp/gl if gl > 0 else (float("inf") if gp > 0 else 0.0)
        mins.append(pf)
    return float(min(mins))


def filter_cost(events, atr, spread, stop_m, max_s):
    kept = []
    for i in events:
        i = int(i); A = atr[i]
        if not np.isfinite(A) or A <= 0: continue
        sd = stop_m * float(A); s = float(spread[i]) if np.isfinite(spread[i]) else 1e9
        if sd > 0 and s/sd <= max_s: kept.append(i)
    return np.array(kept, int)


def make_hyps(df, atr):
    bc = df["BidClose"].to_numpy(float)
    bh = df["BidHigh"].to_numpy(float)
    bl = df["BidLow"].to_numpy(float)
    n = len(df)
    spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
    rsi14, rsi9 = rsi(bc, 14), rsi(bc, 9)
    e10, e20, e30, e50 = ema(bc, 10), ema(bc, 20), ema(bc, 30), ema(bc, 50)
    roll_h = pd.Series(bh).rolling(12).max().to_numpy()
    roll_l = pd.Series(bl).rolling(12).min().to_numpy()
    rng12 = roll_h - roll_l
    hyps = []

    def add(side, fam, raw, stop_m, trail_m, gap, max_s, tag):
        ev = filter_cost(throttle(raw, gap), atr, spread, stop_m, max_s)
        hyps.append(dict(id=f"{side}_{tag}_s{stop_m}_t{trail_m}_g{gap}_sp{max_s}",
            side=side, family=fam, events=ev, stop_atr_mult=stop_m, trail_atr_mult=trail_m))

    configs = [(2.0, 1.0, 12, 0.20), (2.5, 1.0, 16, 0.15), (3.0, 1.25, 20, 0.12), (2.0, 0.75, 12, 0.15)]
    for period, thr in [(14, 75), (14, 80), (9, 75), (9, 80)]:
        r = rsi14 if period == 14 else rsi9
        raw = np.where((np.arange(n) > 60) & (r > thr))[0]
        for sm, tm, g, ms in configs:
            add("SHORT", "rsi_ob", raw, sm, tm, g, ms, f"rsi{period}_ob{thr}")
    for period, thr in [(14, 25), (14, 20), (9, 25), (9, 20)]:
        r = rsi14 if period == 14 else rsi9
        raw = np.where((np.arange(n) > 60) & (r < thr))[0]
        for sm, tm, g, ms in configs[:3]:
            add("LONG", "rsi_os", raw, sm, tm, g, ms, f"rsi{period}_os{thr}")
    for sm, tm, g, ms in [(2.0, 1.0, 12, 0.18), (2.5, 1.0, 16, 0.15), (3.0, 1.25, 20, 0.12)]:
        raw = np.where((np.arange(n) > 60) & (bc > e50) & (bl <= e20) & (bc > e20))[0]
        add("LONG", "ema_pb_l", raw, sm, tm, g, ms, "ema_pb")
        raw = np.where((np.arange(n) > 60) & (bc < e50) & (bh >= e20) & (bc < e20))[0]
        add("SHORT", "ema_pb_s", raw, sm, tm, g, ms, "ema_pb")
    prev_h = np.roll(roll_h, 1); prev_l = np.roll(roll_l, 1); prev_h[0] = np.nan; prev_l[0] = np.nan
    comp = (rng12 / np.where(atr > 0, atr, np.nan)) < 1.2
    for sm, tm, g, ms in [(2.0, 1.0, 16, 0.15), (2.5, 1.0, 20, 0.12)]:
        raw = np.where((np.arange(n) > 60) & comp & (bc > prev_h) & np.isfinite(prev_h))[0]
        add("LONG", "break_l", raw, sm, tm, g, ms, "break_comp")
        raw = np.where((np.arange(n) > 60) & comp & (bc < prev_l) & np.isfinite(prev_l))[0]
        add("SHORT", "break_s", raw, sm, tm, g, ms, "break_comp")
    for sm, tm, g, ms in [(2.5, 1.0, 24, 0.15), (3.0, 1.25, 30, 0.12)]:
        cu = (e10 > e30) & (np.roll(e10, 1) <= np.roll(e30, 1)); cu[0] = False
        cd = (e10 < e30) & (np.roll(e10, 1) >= np.roll(e30, 1)); cd[0] = False
        add("LONG", "ema_x_l", np.where((np.arange(n) > 60) & cu)[0], sm, tm, g, ms, "ema_x")
        add("SHORT", "ema_x_s", np.where((np.arange(n) > 60) & cd)[0], sm, tm, g, ms, "ema_x")
    return hyps


def rnd(x, nd=4):
    try:
        x = float(x)
        return round(x, nd) if np.isfinite(x) else None
    except Exception:
        return None


def eval_hyp(df, atr, hyp, t1, t2):
    ev = hyp["events"]
    val_ev = ev[(ev >= t1) & (ev < t2)]
    test_ev = ev[ev >= t2]
    train_ev = ev[ev < t1]
    sim = simulate_short_broker_correct if hyp["side"] == "SHORT" else simulate_long_broker_correct
    kw = dict(stop_atr_mult=hyp["stop_atr_mult"], trail_atr_mult=hyp["trail_atr_mult"], max_hold=72)

    def run(e):
        if len(e) == 0:
            return None, {"trades": 0, "PF": float("nan"), "avg_R": float("nan"), "max_DD": float("nan")}
        tr = sim(df, atr, e, **kw)
        return tr, trade_metrics(tr)

    tr_v, m_v = run(val_ev)
    _, m_te = run(test_ev)
    _, m_tr = run(train_ev)
    blk = six_block_min_pf(tr_v) if tr_v is not None and len(tr_v) else float("nan")
    vt = int(m_v.get("trades") or 0)
    vp = float(m_v.get("PF") or float("nan"))
    ok = vt > VAL_MIN_TRADES and np.isfinite(vp) and vp > VAL_MIN_PF and np.isfinite(blk) and blk > BLOCK_MIN_PF
    return dict(
        hypothesis_id=hyp["id"], family=hyp["family"], side=hyp["side"],
        stop_atr_mult=hyp["stop_atr_mult"], trail_atr_mult=hyp["trail_atr_mult"],
        n_signals_all=int(len(ev)),
        train_trades=int(m_tr.get("trades") or 0), train_pf=rnd(m_tr.get("PF")),
        val_trades=vt, val_pf=rnd(vp), val_avg_R=rnd(m_v.get("avg_R")), val_max_DD=rnd(m_v.get("max_DD")),
        val_block_min_pf=rnd(blk),
        test_trades=int(m_te.get("trades") or 0), test_pf=rnd(m_te.get("PF")), test_avg_R=rnd(m_te.get("avg_R")),
        pass_gates=bool(ok),
    )


def main():
    rows, winners, near = [], [], []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        df = load_pair(sym)
        if df is None:
            print("  MISSING", flush=True); continue
        atr = wilder_atr14(df["BidHigh"].to_numpy(float), df["BidLow"].to_numpy(float), df["BidClose"].to_numpy(float))
        spread = (df["AskClose"] - df["BidClose"]).to_numpy(float)
        ms, ma = float(np.nanmedian(spread)), float(np.nanmedian(atr[np.isfinite(atr)]))
        ratio = (ms/ma) if ma else float("nan")
        print(f"  rows={len(df)} spread/atr={ratio:.4f}", flush=True)
        t1, t2 = int(0.60 * len(df)), int(0.80 * len(df))
        best = None
        for hyp in make_hyps(df, atr):
            row = eval_hyp(df, atr, hyp, t1, t2)
            row["symbol"] = sym
            row["med_spread"] = round(ms, 8); row["med_atr"] = round(ma, 8)
            rows.append(row)
            if row["pass_gates"]:
                winners.append(row)
                print("  PASS", row["hypothesis_id"], "n=", row["val_trades"], "pf=", row["val_pf"], "blk=", row["val_block_min_pf"], flush=True)
            if (row["val_trades"] or 0) >= 50 and (best is None or (row["val_pf"] or 0) > (best["val_pf"] or 0)):
                best = row
        if best:
            near.append(best)
            print("  best", best["hypothesis_id"], "n=", best["val_trades"], "pf=", best["val_pf"], "blk=", best["val_block_min_pf"], "pass=", best["pass_gates"], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "cost_aware_hypothesis_results.csv", index=False)
    summary = dict(
        gates=dict(split="60/20/20", val_min_trades=VAL_MIN_TRADES, val_min_pf=VAL_MIN_PF,
                   six_block_min_pf=BLOCK_MIN_PF, execution="broker_correct_bid_ask",
                   cost_design="wider stop + max_spread_to_stop filter"),
        n_pairs=len(PAIRS), n_evals=len(rows), n_pass=len(winners),
        winners=winners, best_per_symbol=near,
    )
    (OUT / "cost_aware_hypothesis_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n==== SUMMARY ====", flush=True)
    print(f"Evals={len(rows)} Pass={len(winners)}", flush=True)
    for w in winners:
        print("  WINNER", w["symbol"], w["hypothesis_id"], "val_pf=", w["val_pf"], "test_pf=", w["test_pf"], flush=True)
    if not winners:
        ranked = sorted([r for r in rows if (r.get("val_trades") or 0) > 200 and r.get("val_pf")],
                        key=lambda x: x["val_pf"], reverse=True)[:20]
        print("Top near-misses (val_trades>200):", flush=True)
        for r in ranked:
            print(" ", r["symbol"], r["hypothesis_id"], "n=", r["val_trades"], "pf=", r["val_pf"], "blk=", r["val_block_min_pf"], "test=", r["test_pf"], flush=True)


if __name__ == "__main__":
    main()
