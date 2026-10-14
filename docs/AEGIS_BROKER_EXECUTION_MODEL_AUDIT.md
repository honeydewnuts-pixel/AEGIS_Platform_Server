# AEGIS Broker Execution Model Audit

**Date:** 2026-10-14  
**Scope:** Research evaluation models present in repository (not live MT5 fills)

---

## A. Price sides (required contract)

| Action | Required executable side (FX) |
|--------|-------------------------------|
| BUY entry | Ask |
| BUY exit / stop | Bid |
| SELL entry | Bid |
| SELL exit / stop | Ask |

**V53.6 frozen historical reconstruction (documented):** SHORT entry = next-bar **Ask open**; stop/exit on **Bid** side; costs described as embedded in Bid/Ask (`bid_ask_embedded_v1`). Optional legacy **0.085R** only for legacy reproduction path — must not be double-counted with embedded spread.

**Stage 3 / 3B scripts:** Intended **broker-correct** Bid/Ask fills (see `scripts/stage3_broker_correct_discovery.py`). Outcomes under that contract: **0 selected**.

---

## B. Data authenticity

| Dataset | In Git tree? | Representation | SHA-256 (manifest) |
|---------|--------------|----------------|--------------------|
| `USDCHF_M5_BIDASK_5Y.csv` | **NO** (removed as non-runtime) | Documented as M5 Bid/Ask 5Y | `f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97` |
| Operational replay ledger | YES | Trade-level R under reconstruction | (ledger file) |
| Reproduced trades legacy/bidask | YES | Same 4957 events | verification folder |

**Limitation:** Without the source Bid/Ask CSV in this environment, **new** bar-level discovery cannot be executed. Manifest and prior audits are not a substitute for re-running bar engines.

If Ask was ever reconstructed from Bid + assumed spread, results must be labelled **reconstructed**, not genuine historical Ask.

---

## C. Signal timing

V53.6 path: signal on **closed** bar sequence; entry **next bar** open (Ask for short historical path).  
Do not execute on the same bar that forms the signal using unavailable future information.

---

## D. Stops / targets / intrabar

V53.6: initial stop 1.5 ATR(14); BE +1R; trail 0.75 ATR; max hold 72 M5 bars.  
Intrabar stop vs target ambiguity: candle data cannot always order events; conservative rules required. Repository reconstruction matched stored ledger event-for-event (internal consistency), which does **not** prove tick-level path independence.

---

## E. Broker costs

| Cost | Status |
|------|--------|
| Historical Bid/Ask spread | Embedded in documented reconstruction when Bid/Ask series used |
| Universal 0.085R | Legacy only; **do not** apply on top of embedded Bid/Ask |
| Commission / swap schedules | **Not verified** as broker-account-specific in this audit — do not invent |
| Slippage | Not proven from tick data |

Sensitivity analyses without broker specs must be labelled **assumptions**, not exact historical fills.

---

## F. Lot sizing / risk

Cash-test and sizing artifacts exist under `research/instruments/USDCHF/` and `artifacts/sizing_validation/`.  
Do not confuse stop-loss risk with margin requirement. Contract size, volume step, and account currency must be explicit per broker.

---

## G. Verified vs assumption

| Item | Classification |
|------|----------------|
| Stage 3/3B selected count = 0 under stated gates | **VERIFIED** (JSON artifacts) |
| V53.6 ledger match 4957/4957 | **VERIFIED** (reproduction summary) |
| RSI9 USDCHF invalidated under corrected SHORT fills | **VERIFIED** (execution integrity audit doc) |
| Live broker fill equality to research prices | **UNVERIFIED** |
| Commission/swap for operator’s broker | **UNVERIFIED** |
| Independent executable edge of frozen V53.6 signals under alternate side conventions | Prior investigations reported failure; **not re-run this session** (no source CSV) |

---

## Known limitations

1. Source 5Y Bid/Ask files external to GitHub tree.  
2. In-memory OHLC stream is operational path, not research dataset.  
3. Attractive reconstruction PF ≠ promotion.
