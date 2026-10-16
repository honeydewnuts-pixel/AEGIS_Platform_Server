#!/usr/bin/env python3
"""
Direct market-behaviour study (D1 persistence, D2 vol expansion).
Preregistration: AEGIS_DIRECT_MARKET_BEHAVIOUR_PREREGISTRATION.md
Prereg hash must match outputs/preregistration_hash.txt
No trading rules. No parameter search. Development = first 80% only.
"""
from __future__ import annotations
import json, time, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path("/home/workdir/artifacts/discovery_hypotheses/post_discovery_phase/outputs")
OUT.mkdir(parents=True, exist_ok=True)
PREREG = Path("/home/workdir/artifacts/discovery_hypotheses/post_discovery_phase/docs/AEGIS_DIRECT_MARKET_BEHAVIOUR_PREREGISTRATION.md")
PREREG_HASH_FILE = OUT / "preregistration_hash.txt"

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]
HORIZONS = [6, 12, 24]
L_LOOKBACK = 12
K_ATR = 1.0
ATR_MED_WIN = 100


def wilder_atr14(h, l, c):
    n = len(c)
    tr = np.full(n, np.nan)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    atr[1] = tr[1]
    for k in range(2, n):
        atr[k] = (13.0 * atr[k - 1] + tr[k]) / 14.0
    atr[:14] = np.nan
    return atr


def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    for col, src in [("bh", "bid_high"), ("bl", "bid_low"), ("bc", "bid_close")]:
        df[col] = df[src].astype(float)
    df["spread"] = (df["ask_close"] - df["bid_close"]).astype(float)
    df["hour"] = df["datetime"].dt.hour
    return df


def analyze_pair(sym: str) -> dict:
    df = load(sym)
    n = len(df)
    n_dev = int(0.80 * n)  # development = first 80%; final 20% exposed
    bh = df["bh"].to_numpy(float)
    bl = df["bl"].to_numpy(float)
    bc = df["bc"].to_numpy(float)
    hours = df["hour"].to_numpy(int)
    spread = df["spread"].to_numpy(float)
    atr = wilder_atr14(bh, bl, bc)
    atr_med = pd.Series(atr).shift(1).rolling(ATR_MED_WIN, min_periods=50).median().to_numpy()

    med_spread = float(np.nanmedian(spread[:n_dev]))

    # --- D1 events ---
    results_d1 = []
    for H in HORIZONS:
        signed_rets = []
        cont = []
        uncond_abs = []
        # overlapping events in dev window
        for i in range(max(L_LOOKBACK + 20, 50), n_dev - H):
            A = atr[i]
            if not np.isfinite(A) or A <= 0:
                continue
            move = bc[i] - bc[i - L_LOOKBACK]
            if abs(move) < K_ATR * A:
                continue
            direction = 1.0 if move > 0 else -1.0
            r = bc[i + H] - bc[i]
            signed_rets.append(direction * r)
            cont.append(1.0 if np.sign(r) == np.sign(move) else 0.0)
        # unconditional abs returns on same window
        for i in range(50, n_dev - H, 5):  # subsample every 5 bars
            uncond_abs.append(abs(bc[i + H] - bc[i]))

        # non-overlapping robustness
        no_rets, no_cont = [], []
        next_i = max(L_LOOKBACK + 20, 50)
        while next_i < n_dev - H:
            i = next_i
            A = atr[i]
            if np.isfinite(A) and A > 0:
                move = bc[i] - bc[i - L_LOOKBACK]
                if abs(move) >= K_ATR * A:
                    direction = 1.0 if move > 0 else -1.0
                    r = bc[i + H] - bc[i]
                    no_rets.append(direction * r)
                    no_cont.append(1.0 if np.sign(r) == np.sign(move) else 0.0)
                    next_i = i + H
                    continue
            next_i += 1

        sr = np.array(signed_rets) if signed_rets else np.array([])
        ua = np.array(uncond_abs) if uncond_abs else np.array([])
        nr = np.array(no_rets) if no_rets else np.array([])
        results_d1.append(dict(
            H=H,
            n_events=len(sr),
            mean_signed_ret=float(np.mean(sr)) if len(sr) else None,
            median_signed_ret=float(np.median(sr)) if len(sr) else None,
            cont_rate=float(np.mean(cont)) if cont else None,
            uncond_mean_abs_ret=float(np.mean(ua)) if len(ua) else None,
            mean_vs_uncond_abs=float(np.mean(sr) / np.mean(ua)) if len(sr) and len(ua) and np.mean(ua) > 0 else None,
            mean_over_med_spread=float(np.mean(sr) / med_spread) if len(sr) and med_spread > 0 else None,
            n_nonoverlap=len(nr),
            mean_signed_ret_nonoverlap=float(np.mean(nr)) if len(nr) else None,
            cont_rate_nonoverlap=float(np.mean(no_cont)) if no_cont else None,
        ))

    # --- D2 events ---
    results_d2 = []
    for H in HORIZONS:
        ratios = []
        uncond_ranges = []
        for i in range(ATR_MED_WIN + 20, n_dev - H):
            A = atr[i]
            M = atr_med[i]
            if not np.isfinite(A) or not np.isfinite(M) or A <= 0:
                continue
            # unconditional range sample
            rng = float(np.max(bh[i + 1:i + H + 1]) - np.min(bl[i + 1:i + H + 1]))
            uncond_ranges.append(rng)
            if A < M:  # low vol
                ratios.append(rng / A)

        # non-overlap low-vol
        no_ratios = []
        next_i = ATR_MED_WIN + 20
        while next_i < n_dev - H:
            i = next_i
            A, M = atr[i], atr_med[i]
            if np.isfinite(A) and np.isfinite(M) and A > 0 and A < M:
                rng = float(np.max(bh[i + 1:i + H + 1]) - np.min(bl[i + 1:i + H + 1]))
                no_ratios.append(rng / A)
                next_i = i + H
            else:
                next_i += 1

        ur = np.array(uncond_ranges) if uncond_ranges else np.array([])
        # unconditional ratio uses median ATR as denom proxy
        med_A = float(np.nanmedian(atr[ATR_MED_WIN:n_dev]))
        uncond_ratio_mean = float(np.mean(ur) / med_A) if len(ur) and med_A > 0 else None
        rt = np.array(ratios) if ratios else np.array([])
        results_d2.append(dict(
            H=H,
            n_lowvol_events=len(rt),
            mean_ratio=float(np.mean(rt)) if len(rt) else None,
            median_ratio=float(np.median(rt)) if len(rt) else None,
            uncond_mean_range=float(np.mean(ur)) if len(ur) else None,
            uncond_mean_ratio_proxy=uncond_ratio_mean,
            ratio_vs_uncond=float(np.mean(rt) / uncond_ratio_mean) if len(rt) and uncond_ratio_mean and uncond_ratio_mean > 0 else None,
            n_nonoverlap=len(no_ratios),
            mean_ratio_nonoverlap=float(np.mean(no_ratios)) if no_ratios else None,
        ))

    # stability: first vs second half of dev window (primary H=12)
    half = n_dev // 2
    def half_persistence(lo, hi):
        rets = []
        for i in range(max(L_LOOKBACK + 20, lo), min(hi, n_dev) - 12):
            A = atr[i]
            if not np.isfinite(A) or A <= 0:
                continue
            move = bc[i] - bc[i - L_LOOKBACK]
            if abs(move) < K_ATR * A:
                continue
            direction = 1.0 if move > 0 else -1.0
            rets.append(direction * (bc[i + 12] - bc[i]))
        return float(np.mean(rets)) if rets else None, len(rets)

    m1, n1 = half_persistence(50, half)
    m2, n2 = half_persistence(half, n_dev)

    return dict(
        symbol=sym, rows=n, n_dev=n_dev, med_spread=med_spread,
        d1=results_d1, d2=results_d2,
        stability_H12_first_half_mean=m1, stability_H12_first_half_n=n1,
        stability_H12_second_half_mean=m2, stability_H12_second_half_n=n2,
    )


def main():
    t0 = time.time()
    # verify prereg hash
    actual = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    recorded = PREREG_HASH_FILE.read_text().split()[0] if PREREG_HASH_FILE.exists() else ""
    if actual != recorded:
        print(f"WARNING: prereg hash mismatch actual={actual} recorded={recorded}")
    else:
        print(f"Prereg hash OK: {actual[:16]}...")

    all_results = []
    rows_flat = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        r = analyze_pair(sym)
        all_results.append(r)
        for d1 in r["d1"]:
            rows_flat.append(dict(symbol=sym, study="D1_persistence", **{k: d1[k] for k in d1}))
        for d2 in r["d2"]:
            rows_flat.append(dict(symbol=sym, study="D2_vol_expansion", **{k: d2[k] for k in d2}))
        # print primary H=12
        d1_12 = next(x for x in r["d1"] if x["H"] == 12)
        d2_12 = next(x for x in r["d2"] if x["H"] == 12)
        print(f"  D1 H12 n={d1_12['n_events']} mean_signed={d1_12['mean_signed_ret']} cont={d1_12['cont_rate']} "
              f"vs_spread={d1_12['mean_over_med_spread']} nonoverlap_n={d1_12['n_nonoverlap']}", flush=True)
        print(f"  D2 H12 n={d2_12['n_lowvol_events']} mean_ratio={d2_12['mean_ratio']} "
              f"vs_uncond={d2_12['ratio_vs_uncond']}", flush=True)
        print(f"  stability H12 first={r['stability_H12_first_half_mean']} second={r['stability_H12_second_half_mean']}", flush=True)

    pd.DataFrame(rows_flat).to_csv(OUT / "direct_market_behaviour_results.csv", index=False)
    summary = dict(
        prereg_hash=actual,
        prereg_file=str(PREREG),
        horizons=HORIZONS,
        L_lookback=L_LOOKBACK,
        k_atr=K_ATR,
        development_fraction=0.80,
        final_20_status="EXPOSED_not_used_for_selection",
        n_pairs=len(PAIRS),
        elapsed_sec=round(time.time() - t0, 1),
        per_pair=all_results,
    )
    (OUT / "direct_market_behaviour_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    # Aggregate decision helpers
    d1_primary = [next(x for x in r["d1"] if x["H"] == 12) for r in all_results]
    d2_primary = [next(x for x in r["d2"] if x["H"] == 12) for r in all_results]
    print("\n==== AGGREGATE D1 H=12 ====", flush=True)
    means = [x["mean_signed_ret"] for x in d1_primary if x["mean_signed_ret"] is not None]
    conts = [x["cont_rate"] for x in d1_primary if x["cont_rate"] is not None]
    spreads = [x["mean_over_med_spread"] for x in d1_primary if x["mean_over_med_spread"] is not None]
    print(f"  instruments with data: {len(means)}")
    print(f"  mean of mean_signed_ret: {np.mean(means):.6f}")
    print(f"  mean cont_rate: {np.mean(conts):.4f}")
    print(f"  mean (signed_ret / med_spread): {np.mean(spreads):.3f}")
    print(f"  instruments with mean_signed_ret > 0: {sum(1 for m in means if m > 0)}/{len(means)}")
    print(f"  instruments with |mean|/spread > 1: {sum(1 for s in spreads if abs(s) > 1)}/{len(spreads)}")

    print("\n==== AGGREGATE D2 H=12 ====", flush=True)
    ratios = [x["mean_ratio"] for x in d2_primary if x["mean_ratio"] is not None]
    vs = [x["ratio_vs_uncond"] for x in d2_primary if x["ratio_vs_uncond"] is not None]
    print(f"  mean of mean_ratio: {np.mean(ratios):.4f}")
    print(f"  mean ratio_vs_uncond: {np.mean(vs):.4f}")
    print(f"  instruments with ratio_vs_uncond > 1: {sum(1 for v in vs if v > 1)}/{len(vs)}")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
