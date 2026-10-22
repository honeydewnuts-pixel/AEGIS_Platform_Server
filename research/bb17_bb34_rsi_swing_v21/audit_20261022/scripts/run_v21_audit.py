#!/usr/bin/env python3
"""v2.1 audit: early+late events, target-state reconciliation."""
from __future__ import annotations
import json, hashlib, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from indicators_v21 import compute_stack_v21
from signal_engine_v21 import generate_events, SWING_L, SWING_R
from late_reversal_v21 import detect_late_reversals

DATA = Path("/home/workdir/artifacts/AEGIS_CSV_5Y")
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
PAIRS = ["AUDUSD","EURCHF","EURGBP","EURJPY","EURUSD","GBPJPY","GBPNZD",
         "GBPUSD","NZDCHF","NZDJPY","USDCAD","USDCHF","USDJPY"]

def load(sym):
    p = DATA / f"{sym}_M5_BIDASK_5Y.csv"
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    df = pd.read_csv(p)
    df["datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return df, h

def combined_state_machine(early_events, late_events, n):
    by_bar = defaultdict(list)
    for e in early_events:
        if e.get("eligible"):
            by_bar[e["confirm_idx"]].append(e["action"])
    for e in late_events:
        if e.get("eligible"):
            by_bar[e["decision_idx"]].append(e["action"])
    pos = "FLAT"
    changes = []
    conflicts = 0
    early_ch = late_ch = suppressed = 0
    for i in range(n):
        acts = by_bar.get(i, [])
        if not acts:
            continue
        has_bear = any(a in ("EARLY_BEARISH_REVERSAL", "LATE_BEARISH_REVERSAL") for a in acts)
        has_bull = any(a in ("EARLY_BULLISH_REVERSAL", "LATE_BULLISH_REVERSAL") for a in acts)
        if has_bear and has_bull:
            conflicts += 1
            continue
        if has_bear:
            if pos != "SHORT":
                src = "LATE" if "LATE_BEARISH_REVERSAL" in acts else "EARLY"
                changes.append((i, pos, "SHORT", src))
                early_ch += src == "EARLY"; late_ch += src == "LATE"
                pos = "SHORT"
            else:
                suppressed += 1
        elif has_bull:
            if pos != "LONG":
                src = "LATE" if "LATE_BULLISH_REVERSAL" in acts else "EARLY"
                changes.append((i, pos, "LONG", src))
                early_ch += src == "EARLY"; late_ch += src == "LATE"
                pos = "LONG"
            else:
                suppressed += 1
    return changes, conflicts, early_ch, late_ch, suppressed

def analyze(sym):
    df, h = load(sym)
    c = df["bid_close"].astype(float).to_numpy()
    hi = df["bid_high"].astype(float).to_numpy()
    lo = df["bid_low"].astype(float).to_numpy()
    ind = compute_stack_v21(c, hi, lo)
    early = generate_events(ind)
    late = detect_late_reversals(ind, hi, lo, c)
    elig_e = [e for e in early if e["eligible"]]
    elig_l = [e for e in late if e["eligible"]]
    bear_e = sum(1 for e in elig_e if e["action"] == "EARLY_BEARISH_REVERSAL")
    bull_e = sum(1 for e in elig_e if e["action"] == "EARLY_BULLISH_REVERSAL")
    bear_l = sum(1 for e in elig_l if e["action"] == "LATE_BEARISH_REVERSAL")
    bull_l = sum(1 for e in elig_l if e["action"] == "LATE_BULLISH_REVERSAL")
    changes, conflicts, early_ch, late_ch, suppressed = combined_state_machine(early, late, len(c))
    # early-only target changes for comparison to reported 64084
    from signal_engine_v21 import target_state_machine
    _, ch_early_only, conf_early = target_state_machine(early, len(c))
    years = defaultdict(lambda: {"bear": 0, "bull": 0})
    for e in elig_e:
        y = str(df.loc[e["confirm_idx"], "datetime"].year)
        if e["action"] == "EARLY_BEARISH_REVERSAL":
            years[y]["bear"] += 1
        else:
            years[y]["bull"] += 1
    return dict(
        symbol=sym, sha256=h, rows=len(df),
        first_ts=str(df["datetime"].iloc[0]), last_ts=str(df["datetime"].iloc[-1]),
        early_bear=bear_e, early_bull=bull_e, early_total=bear_e + bull_e,
        late_bear=bear_l, late_bull=bull_l, late_total=bear_l + bull_l,
        target_changes_with_late=len(changes),
        target_changes_early_only=len(ch_early_only),
        conflicts=conflicts, conflicts_early_only=conf_early,
        early_driven_changes=early_ch, late_driven_changes=late_ch,
        suppressed_same_dir=suppressed,
        unique_swing_source=len({e["extreme_idx"] for e in elig_e}),
        unique_confirm=len({e["confirm_idx"] for e in elig_e}),
        year_counts=dict(years),
    )

from collections import defaultdict

def main():
    rows = []
    for sym in PAIRS:
        print(f"=== {sym} ===", flush=True)
        r = analyze(sym)
        rows.append(r)
        print(f"  early={r['early_total']} late={r['late_total']} ch_early={r['target_changes_early_only']} ch_all={r['target_changes_with_late']} conf={r['conflicts']}", flush=True)
        pd.DataFrame(rows).to_csv(OUT / "audit_per_instrument.csv", index=False)
    te = sum(r["early_total"] for r in rows)
    tb = sum(r["early_bear"] for r in rows)
    tu = sum(r["early_bull"] for r in rows)
    tl = sum(r["late_total"] for r in rows)
    ce = sum(r["target_changes_early_only"] for r in rows)
    ca = sum(r["target_changes_with_late"] for r in rows)
    summary = dict(
        research_id="BB17_BB34_RSI_SWING_V2.1_AUDIT_20261022",
        production_authorized=False, execution_authorized=False,
        reported_early_total=167412, reproduced_early_total=te,
        reported_bear=88454, reproduced_bear=tb,
        reported_bull=78958, reproduced_bull=tu,
        early_sum_ok=(tb + tu == te), early_match_reported=(te == 167412),
        reported_target_changes=64084, reproduced_target_changes_early_only=ce,
        reproduced_target_changes_with_late=ca,
        early_only_match_reported=(ce == 64084),
        total_late_events=tl,
        total_conflicts=sum(r["conflicts"] for r in rows),
        n_pairs=len(rows),
        definitions={
            "eligible_event": "Confirmed swing/sequence meeting frozen conditions",
            "signal": "Eligible event at confirm/decision row",
            "target_state_change": "FLAT/LONG/SHORT transition under single-position machine",
            "trade": "NOT counted — no cash model",
        },
        instruments=rows,
    )
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nEARLY {te} (bear {tb} bull {tu}) match={te==167412}")
    print(f"LATE {tl} CH_EARLY {ce} match64084={ce==64084} CH_ALL {ca}")
    print("DONE")

if __name__ == "__main__":
    main()
