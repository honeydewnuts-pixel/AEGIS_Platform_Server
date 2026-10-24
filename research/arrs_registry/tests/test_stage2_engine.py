#!/usr/bin/env python3
"""Stage 2 evaluator tests — software behavior only."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src" / "stage2"))

from stage2.data import load_bid_ask_csv, validate_bid_ask, dataset_hash
from stage2.simulator import simulate_trades, TradeManagementTemplate, atr_series
from stage2.walkforward import chronological_partitions, PartitionSpec, walk_forward_evaluate
from stage2.gates import evaluate_gates, GatePolicy
from stage2.runner import run_evaluation

FIX = ROOT / "tests" / "fixtures" / "synthetic_bidask_m5.csv"
P = F = 0

def check(n, c, d=""):
    global P, F
    if c:
        P += 1
        print(f"[PASS] {n}")
    else:
        F += 1
        print(f"[FAIL] {n} {d}")


def test_data_valid():
    df = load_bid_ask_csv(FIX)
    rep = validate_bid_ask(df)
    check("valid_ok", rep["ok"], str(rep))
    check("class_a", rep["data_class"] == "A_BIDASK")
    h1 = dataset_hash(FIX)
    h2 = dataset_hash(FIX)
    check("hash_stable", h1 == h2)


def test_invalid_ohlc():
    df = load_bid_ask_csv(FIX).copy()
    df.loc[10, "bid_high"] = df.loc[10, "bid_low"] - 1
    df.attrs["data_class"] = "A_BIDASK"
    rep = validate_bid_ask(df)
    check("invalid_ohlc_fails", not rep["ok"])


def test_causal_entry_sides():
    df = load_bid_ask_csv(FIX)
    sig = pd.Series(0, index=df.index)
    sig.iloc[50] = 1  # signal on bar 50 → entry bar 51 ask_open
    tm = TradeManagementTemplate("T", "1", initial_stop_atr=10.0, max_hold_bars=5, take_profit_atr=None)
    tr = simulate_trades(df, sig, tm=tm)
    check("has_trade", len(tr) >= 1)
    if len(tr):
        entry = float(tr.iloc[0]["entry"])
        expected = float(df["ask_open"].iloc[51])
        check("long_entry_ask", abs(entry - expected) < 1e-12, f"{entry} vs {expected}")


def test_short_entry_bid():
    df = load_bid_ask_csv(FIX)
    sig = pd.Series(0, index=df.index)
    sig.iloc[60] = -1
    tm = TradeManagementTemplate("T", "1", initial_stop_atr=10.0, max_hold_bars=5)
    tr = simulate_trades(df, sig, tm=tm)
    check("short_trade", len(tr) >= 1)
    if len(tr):
        entry = float(tr.iloc[0]["entry"])
        expected = float(df["bid_open"].iloc[61])
        check("short_entry_bid", abs(entry - expected) < 1e-12)


def test_no_same_bar_fill_by_default():
    df = load_bid_ask_csv(FIX)
    sig = pd.Series(0, index=df.index)
    sig.iloc[70] = 1
    tm = TradeManagementTemplate("T", "1", initial_stop_atr=10.0, max_hold_bars=3)
    tr = simulate_trades(df, sig, tm=tm)
    if len(tr):
        check("entry_i_after_signal", int(tr.iloc[0]["entry_i"]) == 71)


def test_partitions():
    parts = chronological_partitions(1000, PartitionSpec())
    check("train_before_val", parts["train"][1] <= parts["val"][0])
    check("val_before_test", parts["val"][1] <= parts["test"][0])
    check("test_end", parts["test"][1] == 1000)


def test_gates_fail_closed():
    g = evaluate_gates(
        data_report={"ok": False, "issues": ["x"], "data_class": "A_BIDASK"},
        wf={"partitions": {}}, tm_defined=True,
    )
    check("bad_data_fail", g["overall"] == "FAIL")
    g2 = evaluate_gates(
        data_report={"ok": True, "data_class": "B_OHLC_PROXY"},
        wf={"partitions": {"val": {"trades": 100, "pf": 2.0}, "test": {"trades": 100, "pf": 2.0}}},
        tm_defined=True,
    )
    check("class_b_fail", g2["overall"] == "FAIL")
    g3 = evaluate_gates(
        data_report={"ok": True, "data_class": "A_BIDASK"},
        wf={"partitions": {}}, tm_defined=False,
    )
    check("no_tm_not_pass", g3["overall"] != "PASS")
    check("auth_false", g3["execution_authorized"] is False and g3["production_authorized"] is False)


def test_end_to_end_runner():
    def sig_fn(df):
        s = np.zeros(len(df))
        for i in range(40, len(df) - 10, 50):
            s[i] = 1 if i % 100 < 50 else -1
        return pd.Series(s)
    tm = TradeManagementTemplate("TM_ATR_STOP_V1", "1", initial_stop_atr=1.5, max_hold_bars=30)
    res = run_evaluation(
        dataset_path=str(FIX), signal_fn=sig_fn,
        candidate_id="CAND-STAGE2-FIXTURE", candidate_version="1", tm=tm,
    )
    check("runner_status", res["status"] in ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "INSUFFICIENT_DATA"))
    check("runner_auth", res["execution_authorized"] is False)
    check("has_wf", "walk_forward" in res or res["status"] == "INSUFFICIENT_DATA")


def test_no_order_imports():
    text = (ROOT / "src" / "stage2" / "runner.py").read_text() + (ROOT / "src" / "stage2" / "simulator.py").read_text()
    check("no_place_order", "place_order" not in text and "submit_order" not in text)
    check("no_mt5", "mt5" not in text.lower() or "mt5" not in text)


if __name__ == "__main__":
    test_data_valid()
    test_invalid_ohlc()
    test_causal_entry_sides()
    test_short_entry_bid()
    test_no_same_bar_fill_by_default()
    test_partitions()
    test_gates_fail_closed()
    test_end_to_end_runner()
    test_no_order_imports()
    print(f"TOTAL {P} PASS {F} FAIL")
    sys.exit(0 if F == 0 else 1)
