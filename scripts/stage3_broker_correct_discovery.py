#!/usr/bin/env python3
"""Stage 3 — Broker-Correct Discovery (Generation 2). production_authorized=false always."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.rulebooks.evaluators.common import (
    wilder_atr14, trade_metrics,
    simulate_short_broker_correct, simulate_long_broker_correct,
)

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = ROOT / "artifacts" / "stage3_broker_correct"
OUT.mkdir(parents=True, exist_ok=True)
PAIRS = [
    "AUDUSD","EURCHF","EURGBP","EURJPY","EURUSD","GBPJPY",
    "GBPNZD","GBPUSD","NZDCHF","NZDJPY","USDCAD","USDCHF","USDJPY",
]
VAL_MIN_TRADES, VAL_MIN_PF, VAL_MIN_BLOCK = 200, 1.6, 1.0
TEST_MIN_PF, TEST_MIN_BLOCK = 1.0, 1.0


def load(sym: str):
    path = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    if not path.is_file():
        return None, {"error": "missing"}
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    df = pd.read_csv(path)
    lower = {c.lower(): c for c in df.columns}
    def pick(*ns):
        for n in ns:
            if n in df.columns: return n
            if n.lower() in lower: return lower[n.lower()]
        return None
    ts = pick("timestamp", "datetime", "time")
    df["datetime"] = pd.to_datetime(df[ts], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    for std, alt in [
        ("BidOpen","bid_open"),("BidHigh","bid_high"),("BidLow","bid_low"),("BidClose","bid_close"),
        ("AskOpen","ask_open"),("AskHigh","ask_high"),("AskLow","ask_low"),("AskClose","ask_close"),
    ]:
        s = pick(std, alt)
        if s:
            df[std] = df[s].astype(float)
    meta = {"symbol": sym, "sha256": sha, "rows": len(df),
            "start": str(df.datetime.iloc[0]), "end": str(df.datetime.iloc[-1])}
    return df, meta


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
    if len(idx) == 0: return idx
    out = [int(idx[0])]
    for i in idx[1:]:
        if int(i) - out[-1] >= gap:
            out.append(int(i))
    return np.array(out, int)


def six_block(tr, i0, i1, blocks=6):
    if tr is None or len(tr) == 0: return 0.0
    w = max(i1 - i0, 1); pfs = []
    for b in range(blocks):
        lo = i0 + int(w * b / blocks); hi = i0 + int(w * (b + 1) / blocks)
        sub = tr[(tr.event_i >= lo) & (tr.event_i < hi)]
        m = trade_metrics(sub)
        pfs.append(m["PF"] if m["trades"] > 0 and np.isfinite(m["PF"]) else 0.0)
    return float(min(pfs))


def eval_split(tr, n):
    a, b = int(n * 0.6), int(n * 0.8)
    def part(lo, hi):
        sub = tr[(tr.event_i >= lo) & (tr.event_i < hi)] if len(tr) else tr
        return trade_metrics(sub), six_block(tr, lo, hi)
    va, vb = part(a, b); te, tb = part(b, n)
    ok = (
        va["trades"] >= VAL_MIN_TRADES and (va["PF"] or 0) > VAL_MIN_PF and vb > VAL_MIN_BLOCK
        and (te["PF"] or 0) >= TEST_MIN_PF and tb >= TEST_MIN_BLOCK
    )
    return va, vb, te, tb, ok


def main():
    winners, nearmiss = [], []
    print("Stage 3 Broker-Correct Discovery", flush=True)
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        df, meta = load(sym)
        if df is None:
            print("  missing data", flush=True)
            continue
        n = len(df)
        atr = wilder_atr14(df.BidHigh.to_numpy(float), df.BidLow.to_numpy(float), df.BidClose.to_numpy(float))
        mid = ((df.BidClose + df.AskClose) / 2).to_numpy(float)
        best = None
        specs = []
        for p in (7, 9, 14):
            for thr in (65, 70, 75):
                specs.append(("S", "rsi_ob", {"period": p, "thr": thr}))
            for thr in (25, 30, 35):
                specs.append(("L", "rsi_os", {"period": p, "thr": thr}))
        for f, s in ((10, 30), (20, 50)):
            specs.append(("S", "ema_pb_s", {"f": f, "s": s}))
            specs.append(("L", "ema_pb_l", {"f": f, "s": s}))
        for win in (40, 60):
            z = (mid - pd.Series(mid).rolling(win).mean().to_numpy()) / (
                pd.Series(mid).rolling(win).std().to_numpy() + 1e-12
            )
            for thr in (1.5, 2.0):
                specs.append(("L", "zscore_os", {"win": win, "thr": thr, "_z": z}))
                specs.append(("S", "zscore_ob", {"win": win, "thr": thr, "_z": z}))

        for side, fam, params in specs:
            z = params.get("_z")
            if fam == "rsi_ob":
                r = rsi(mid, params["period"]); ev = np.where((~np.isnan(r)) & (r > params["thr"]))[0]
            elif fam == "rsi_os":
                r = rsi(mid, params["period"]); ev = np.where((~np.isnan(r)) & (r < params["thr"]))[0]
            elif fam == "ema_pb_s":
                ef, es = ema(mid, params["f"]), ema(mid, params["s"])
                prev = np.roll(mid, 1); prev[0] = mid[0]
                ev = np.where((ef < es) & (prev < ef) & (mid >= ef) & (~np.isnan(es)))[0]
            elif fam == "ema_pb_l":
                ef, es = ema(mid, params["f"]), ema(mid, params["s"])
                prev = np.roll(mid, 1); prev[0] = mid[0]
                ev = np.where((ef > es) & (prev > ef) & (mid <= ef) & (~np.isnan(es)))[0]
            elif fam == "zscore_os":
                ev = np.where((~np.isnan(z)) & (z < -params["thr"]))[0]
            else:
                ev = np.where((~np.isnan(z)) & (z > params["thr"]))[0]
            ev = throttle(ev.astype(int), 12)
            if len(ev) < 80:
                continue
            for stop, trail in ((1.0, 0.5), (1.5, 0.75)):
                if side == "S":
                    tr = simulate_short_broker_correct(df, atr, ev, stop_atr_mult=stop, trail_atr_mult=trail, max_hold=72)
                else:
                    tr = simulate_long_broker_correct(df, atr, ev, stop_atr_mult=stop, trail_atr_mult=trail, max_hold=72)
                va, vb, te, tb, ok = eval_split(tr, n)
                row = {
                    "symbol": sym, "side": "SHORT" if side == "S" else "LONG", "family": fam,
                    "params": {k: v for k, v in params.items() if k != "_z"},
                    "stop_atr": stop, "trail_atr": trail,
                    "val_pf": None if va["PF"] != va["PF"] else float(va["PF"]),
                    "val_n": float(va["trades"]), "val_blk": vb,
                    "test_pf": None if te["PF"] != te["PF"] else float(te["PF"]),
                    "test_n": float(te["trades"]), "test_blk": tb,
                    "pass": ok, "dataset": meta,
                }
                if best is None or (row["val_pf"] or 0) > (best["val_pf"] or 0):
                    best = row
                if ok:
                    winners.append(row)
        if best:
            nearmiss.append(best)
            print(f"  best val_pf={best['val_pf']} n={best['val_n']:.0f} "
                  f"test_pf={best['test_pf']} pass={best['pass']} {best['side']} {best['family']}", flush=True)

    # write rulebooks for winners only
    rb_dir = ROOT / "registry" / "v41" / "rulebooks_broker_correct"
    rb_dir.mkdir(parents=True, exist_ok=True)
    # best per symbol+side among winners
    selected = {}
    for w in winners:
        key = (w["symbol"], w["side"])
        score = (w["val_pf"] or 0) * np.log1p(w["val_n"] or 0)
        if key not in selected or score > (selected[key]["val_pf"] or 0) * np.log1p(selected[key]["val_n"] or 0):
            selected[key] = w
    written = []
    for w in selected.values():
        rid = f"AEGIS-RB-BC-V1-{w['side']}-{w['family'].upper()}-{w['symbol']}-M5"
        rb = {
            "schema_version": "1.0",
            "rulebook_id": rid,
            "instrument": w["symbol"],
            "timeframe": "M5",
            "direction": f"{w['side']}_ONLY",
            "family": w["family"],
            "params": w["params"],
            "exit": {"initial_stop_atr": w["stop_atr"], "trailing_stop_atr": w["trail_atr"],
                     "max_hold_bars": 72, "break_even": "+1R"},
            "execution": {
                "contract": "broker_correct_v1",
                "long_open": "ASK", "long_close": "BID",
                "short_open": "BID", "short_close": "ASK",
                "entry_timing": "next_bar", "no_universal_0_085R": True,
            },
            "qualification": {
                "validation_trades": w["val_n"], "validation_profit_factor": w["val_pf"],
                "validation_block_min_pf": w["val_blk"],
                "final_test_trades": w["test_n"], "final_test_profit_factor": w["test_pf"],
                "final_test_block_min_pf": w["test_blk"], "gates_passed": True,
            },
            "dataset": w["dataset"],
            "status": "BROKER_CORRECT_RESEARCH_CANDIDATE",
            "production_authorized": False,
            "generation": "stage3_broker_correct_v1",
        }
        path = rb_dir / f"{w['symbol']}_{w['side']}_{w['family']}.json"
        path.write_text(json.dumps(rb, indent=2) + "\n")
        written.append(str(path.relative_to(ROOT)))
        print(f"PASS {w['symbol']} {w['side']} {w['family']} valPF={w['val_pf']} testPF={w['test_pf']}", flush=True)

    report = {
        "stage": "3_broker_correct_discovery",
        "gates": {"val_min_trades": VAL_MIN_TRADES, "val_min_pf": VAL_MIN_PF,
                  "val_min_block_pf": VAL_MIN_BLOCK, "test_min_pf": TEST_MIN_PF,
                  "test_min_block_pf": TEST_MIN_BLOCK},
        "n_winners_raw": len(winners),
        "n_selected": len(selected),
        "selected": list(selected.values()),
        "nearmiss_best_per_symbol": nearmiss,
        "rulebooks": written,
        "production_authorized": False,
    }
    # strip non-serializable
    for row in report["selected"] + report["nearmiss_best_per_symbol"]:
        row.pop("dataset", None)
    (OUT / "STAGE3_DISCOVERY_REPORT.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"Selected {len(selected)} rulebooks; production_authorized=false", flush=True)


if __name__ == "__main__":
    main()
