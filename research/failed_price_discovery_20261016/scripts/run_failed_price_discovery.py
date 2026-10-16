#!/usr/bin/env python3
"""
Failed price discovery measurement study.
Preregistration committed at 4915c357d09a532849f4c15b0e153742351f5797
Hash must match outputs/preregistration_hash.txt before trusting outcomes.
"""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
PREREG = ROOT / "docs/AEGIS_FAILED_PRICE_DISCOVERY_PREREGISTRATION.md"
PREREG_HASH_FILE = OUT / "preregistration_hash.txt"

PAIRS = [
    "AUDUSD", "EURCHF", "EURGBP", "EURJPY", "EURUSD",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCHF", "NZDJPY",
    "USDCAD", "USDCHF", "USDJPY",
]
L = 48
H_FAIL = 12
HORIZONS = [6, 12, 24]
H_STAR = 12
N_BOOT = 1000
SEED = 42
MIN_EVENTS = 50


def load(sym: str) -> pd.DataFrame:
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df["bh"] = df["bid_high"].astype(float)
    df["bl"] = df["bid_low"].astype(float)
    df["bc"] = df["bid_close"].astype(float)
    df["spread"] = (df["ask_close"] - df["bid_close"]).astype(float)
    df["date"] = df["datetime"].dt.date
    return df


def find_events(df: pd.DataFrame, n_dev: int):
    """Return list of event dicts with confirmation in development window."""
    bh = df["bh"].to_numpy(float)
    bl = df["bl"].to_numpy(float)
    bc = df["bc"].to_numpy(float)
    n = n_dev
    events = []
    t = L
    while t < n - H_FAIL - max(HORIZONS) - 1:
        # boundary from t-L .. t-1
        b_hi = float(np.max(bh[t - L:t]))
        b_lo = float(np.min(bl[t - L:t]))
        # scan forward for first break attempt starting at t
        # We iterate t as potential first-break bar
        up = bh[t] > b_hi
        dn = bl[t] < b_lo
        if not up and not dn:
            t += 1
            continue
        # if both (rare), prefer the side with larger excursion
        if up and dn:
            if (bh[t] - b_hi) >= (b_lo - bl[t]):
                dn = False
            else:
                up = False
        direction = -1 if up else 1  # return direction after failure
        t0 = t
        boundary = b_hi if up else b_lo
        # find failure within H_FAIL
        t_f = None
        for j in range(t0 + 1, min(t0 + H_FAIL + 1, n)):
            if up and bc[j] < boundary:
                t_f = j
                break
            if dn and bc[j] > boundary:
                t_f = j
                break
        if t_f is None:
            t = t0 + 1
            continue
        # need room for max horizon
        if t_f + max(HORIZONS) >= n:
            break
        events.append(dict(
            t0=t0, t_f=t_f, direction=direction, boundary=boundary,
            side="up_fail" if up else "down_fail",
            date=str(df.loc[t_f, "date"]),
            confirm_close=float(bc[t_f]),
        ))
        t = t0 + 1
    return events


def dedupe(events, cooldown=H_STAR):
    if not events:
        return []
    events = sorted(events, key=lambda e: e["t_f"])
    out = []
    last_tf = -10**9
    for e in events:
        if e["t_f"] >= last_tf + cooldown:
            out.append(e)
            last_tf = e["t_f"]
    return out


def signed_returns(df, events, H):
    bc = df["bc"].to_numpy(float)
    rs = []
    for e in events:
        tf = e["t_f"]
        r = e["direction"] * (float(bc[tf + H]) - float(bc[tf]))
        rs.append(r)
    return np.array(rs, dtype=float)


def block_bootstrap_mean_ci(r: np.ndarray, dates: list, n_boot=N_BOOT, seed=SEED):
    """Cluster by calendar date of confirmation."""
    if len(r) == 0:
        return None, (None, None), 0
    df = pd.DataFrame({"r": r, "date": dates})
    groups = [g["r"].to_numpy() for _, g in df.groupby("date")]
    n_blocks = len(groups)
    if n_blocks == 0:
        return float(np.mean(r)), (None, None), 0
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        idx = rng.integers(0, n_blocks, size=n_blocks)
        sample = np.concatenate([groups[i] for i in idx])
        means.append(float(np.mean(sample)))
    means = np.array(means)
    lo, hi = float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
    return float(np.mean(r)), (lo, hi), n_blocks


def analyze(sym: str) -> dict:
    df = load(sym)
    n = len(df)
    n_dev = int(0.80 * n)
    med_spread = float(np.nanmedian(df["spread"].to_numpy(float)[:n_dev]))
    raw = find_events(df, n_dev)
    ded = dedupe(raw, cooldown=H_STAR)
    # outcomes
    results = {}
    for H in HORIZONS:
        r_raw = signed_returns(df, raw, H)
        r_ded = signed_returns(df, ded, H)
        dates_ded = [e["date"] for e in ded]
        mean_r, ci, n_day = block_bootstrap_mean_ci(r_ded, dates_ded)
        cont = float(np.mean(r_ded > 0)) if len(r_ded) else None
        results[f"H{H}"] = dict(
            n_raw=len(r_raw),
            n_dedup=len(r_ded),
            mean_signed=mean_r,
            median_signed=float(np.median(r_ded)) if len(r_ded) else None,
            cont_rate=cont,
            mean_over_spread=(mean_r / med_spread) if mean_r is not None and med_spread > 0 else None,
            ci95_lo=ci[0] if ci else None,
            ci95_hi=ci[1] if ci else None,
            n_day_blocks=n_day,
        )
    # stability halves on dedup H*
    half = n_dev // 2
    e1 = [e for e in ded if e["t_f"] < half]
    e2 = [e for e in ded if e["t_f"] >= half]
    m1 = float(np.mean(signed_returns(df, e1, H_STAR))) if e1 else None
    m2 = float(np.mean(signed_returns(df, e2, H_STAR))) if e2 else None
    # by side
    up = [e for e in ded if e["side"] == "up_fail"]
    dn = [e for e in ded if e["side"] == "down_fail"]
    primary = results[f"H{H_STAR}"]
    sufficient = (primary["n_dedup"] or 0) >= MIN_EVENTS
    ci_excludes_0 = (
        primary["ci95_lo"] is not None and primary["ci95_hi"] is not None
        and (primary["ci95_lo"] > 0 or primary["ci95_hi"] < 0)
    )
    return dict(
        symbol=sym, rows=n, n_dev=n_dev, med_spread=med_spread,
        n_raw_events=len(raw), n_dedup_events=len(ded),
        n_up_fail=len(up), n_down_fail=len(dn),
        sufficient=sufficient,
        primary=primary,
        all_H=results,
        stability_first_half_mean=m1, stability_first_half_n=len(e1),
        stability_second_half_mean=m2, stability_second_half_n=len(e2),
        mean_up=float(np.mean(signed_returns(df, up, H_STAR))) if up else None,
        mean_down=float(np.mean(signed_returns(df, dn, H_STAR))) if dn else None,
        ci_excludes_0=ci_excludes_0,
    )


def main():
    t0 = time.time()
    actual = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    recorded = PREREG_HASH_FILE.read_text().split()[0]
    assert actual == recorded, f"prereg hash mismatch {actual} vs {recorded}"
    print(f"Prereg hash OK {actual[:16]}...", flush=True)

    rows = []
    summaries = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        r = analyze(sym)
        summaries.append(r)
        p = r["primary"]
        print(
            f"  dedup n={p['n_dedup']} mean={p['mean_signed']} cont={p['cont_rate']} "
            f"vs_spread={p['mean_over_spread']} CI=[{p['ci95_lo']},{p['ci95_hi']}] "
            f"days={p['n_day_blocks']} suff={r['sufficient']}",
            flush=True,
        )
        for H, hr in r["all_H"].items():
            rows.append(dict(symbol=sym, horizon=H, **hr, med_spread=r["med_spread"],
                             sufficient=r["sufficient"],
                             stab1=r["stability_first_half_mean"], stab2=r["stability_second_half_mean"]))

    pd.DataFrame(rows).to_csv(OUT / "failed_price_discovery_results.csv", index=False)

    # Decision aggregation
    suff = [s for s in summaries if s["sufficient"]]
    pos = [s for s in suff if (s["primary"]["mean_signed"] or 0) > 0]
    ci_pos = [s for s in suff if s["ci_excludes_0"] and (s["primary"]["mean_signed"] or 0) > 0]
    econ = [s for s in suff if s["primary"]["mean_over_spread"] is not None and abs(s["primary"]["mean_over_spread"]) >= 1]

    decision = "INCONCLUSIVE"
    if len(suff) < 5:
        decision = "INCONCLUSIVE"
    elif len(pos) == 0 or all((s["primary"]["mean_signed"] or 0) <= 0 for s in suff):
        decision = "REJECT"
    elif len(ci_pos) >= 5 and len(econ) >= 5:
        # still not tradable — supportive measurement only
        decision = "SUPPORTIVE_NOT_TRADABLE"
    else:
        # mixed / weak
        decision = "REJECT" if len(pos) < len(suff) / 2 else "INCONCLUSIVE"

    summary = dict(
        prereg_hash=actual,
        prereg_commit="4915c357d09a532849f4c15b0e153742351f5797",
        L=L, H_fail=H_FAIL, H_star=H_STAR, horizons=HORIZONS,
        development_fraction=0.80, final_20="EXPOSED",
        n_pairs=len(PAIRS),
        n_sufficient=len(suff),
        n_positive_mean=len(pos),
        n_ci_excludes_0_positive=len(ci_pos),
        n_econ_ge1_spread=len(econ),
        decision=decision,
        elapsed_sec=round(time.time() - t0, 1),
        per_pair=[{
            "symbol": s["symbol"],
            "n_dedup": s["primary"]["n_dedup"],
            "mean_signed": s["primary"]["mean_signed"],
            "cont_rate": s["primary"]["cont_rate"],
            "mean_over_spread": s["primary"]["mean_over_spread"],
            "ci95": [s["primary"]["ci95_lo"], s["primary"]["ci95_hi"]],
            "sufficient": s["sufficient"],
            "stability": [s["stability_first_half_mean"], s["stability_second_half_mean"]],
        } for s in summaries],
    )
    (OUT / "failed_price_discovery_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\n==== DECISION ====", flush=True)
    print(f"sufficient instruments: {len(suff)}/{len(PAIRS)}", flush=True)
    print(f"positive mean: {len(pos)}  CI excludes 0 (pos): {len(ci_pos)}  |mean|/spread>=1: {len(econ)}", flush=True)
    print(f"DECISION: {decision}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
