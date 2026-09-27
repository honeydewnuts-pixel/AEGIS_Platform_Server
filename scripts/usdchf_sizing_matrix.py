"""
USDCHF validation matrix for stop-loss risk sizing (not full historical cash replay).

Produces sizing audit rows for equity x risk% combinations using a fixed
illustrative stop distance. Full 5y operational cash tests require the
USDCHF Bid/Ask dataset (not present in this repository checkout).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.services.position_sizing_engine import (
    default_spec_for_symbol,
    fx_rates_for_pair_price,
    size_by_stop_risk,
)

EQUITIES = [100, 500, 1000, 5000, 10000]
RISK_PCTS = [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
# Illustrative mid + 1.5*ATR-style stop (15 pips on USDCHF)
ENTRY = 0.90000
STOP = 0.90150


def main() -> None:
    spec = default_spec_for_symbol("USDCHF")
    assert spec is not None
    rates = fx_rates_for_pair_price("USDCHF", ENTRY)
    rows = []
    for eq in EQUITIES:
        for pct in RISK_PCTS:
            r = size_by_stop_risk(
                equity=float(eq),
                risk_pct=float(pct),
                entry_price=ENTRY,
                stop_loss=STOP,
                side="SELL",
                spec=spec,
                account_currency="USD",
                fx_rates=rates,
            )
            rows.append(
                {
                    "instrument": "USDCHF",
                    "equity": eq,
                    "risk_pct": pct,
                    "entry": ENTRY,
                    "stop": STOP,
                    "allow": r.allow,
                    "volume": r.volume,
                    "reason": r.reason,
                    "estimated_risk": r.audit.get("estimated_monetary_risk"),
                    "loss_per_lot_usd": r.audit.get("loss_per_lot_account_ccy"),
                    "budget": r.audit.get("risk_budget_used"),
                }
            )
    out_dir = Path("artifacts/sizing_validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "USDCHF_sizing_matrix.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = {
        "instrument": "USDCHF",
        "note": (
            "Sizing matrix only. Full V53.6 operational cash-test ledgers require "
            "five-year USDCHF Bid/Ask CSV (not in repo)."
        ),
        "n_scenarios": len(rows),
        "accepted": sum(1 for r in rows if r["allow"]),
        "rejected": sum(1 for r in rows if not r["allow"]),
        "csv": str(csv_path),
    }
    (out_dir / "USDCHF_sizing_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
