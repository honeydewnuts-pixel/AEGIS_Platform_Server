# AEGIS Rulebook Discovery Status

**Branch:** `research/broker-realistic-discovery-20261014`  
**Base main HEAD:** `f546af71b88b250f7a30d6614d74b6d818505177`  
**Report date:** 2026-10-14  
**production_authorized:** false (unchanged)

---

## 1. Research state at start of this assignment

| Stream | Status | Promotion |
|--------|--------|-----------|
| V53.6 SHORT (frozen) | REPRODUCTION VERIFIED vs stored ledger; historical reconstruction only | **NO** |
| RSI9 SHORT transfer | RESEARCH ONLY; USDCHF **INVALIDATED** under broker-correct SHORT fills | **NO** |
| Native LONG transfer | RESEARCH ONLY; fails broker-correct gates | **NO** |
| Stage 3 broker-correct discovery | **n_selected = 0**, **n_winners_raw = 0** | **NO** |
| Stage 3B multi-TF | **n_selected = 0**, **n_winners = 0** | **NO** |
| Generation 3 | Closed with 0 qualified candidates | **NO** |

Authoritative summary already in-repo: `docs/RESEARCH_STATUS_AND_PRODUCTION_BOUNDARY.md`.

---

## 2. Work completed in this run

1. Verified main HEAD and research artifact locations.
2. Confirmed **USDCHF 5Y Bid/Ask source CSV is not present** in the GitHub tree (removed earlier as non-runtime; see `docs/AEGIS_STAGE2B_ACCEPTANCE_REPORT.md`). Manifest still records SHA-256 `f93d6440…` and 38,311,813 bytes.
3. Recomputed metrics from committed reproduction CSVs (4957 trades):
   - Legacy cost path: PF ≈ **2.3265**
   - Bid/Ask-embedded reconstruction path: PF ≈ **2.6532**
   - Mean R delta bidask−legacy ≈ **+0.085R** (matches documented legacy cost difference)
4. Chronological year blocks on operational ledger (diagnostic only): all yearly PFs remain &gt; 2 under that reconstruction model.
5. Ingested Stage 3 near-miss table into `docs/AEGIS_DISCOVERY_EXPERIMENT_REGISTER.csv` — **all REJECTED** under gates val_pf ≥ 1.6 / block ≥ 1.0.
6. Documented execution-model audit and baseline reproduction limitations (companion docs).

**Not completed (blocked):** New discovery search over 5Y Bid/Ask bars — **source CSV absent** from this environment. Cannot honestly re-run Stage 3/3B or independent executable-edge requalification without restoring the dataset.

---

## 3. Why prior Rulebooks were not adopted

| Candidate class | Confirmed reason for non-adoption |
|-----------------|-----------------------------------|
| Attractive RSI9/Native transfer PFs | **Execution-model error** when SHORT/LONG fills use correct Bid/Ask sides; independent audit marked USDCHF RSI9 INVALIDATED (PF collapsed to ~0.49–0.51). |
| Stage 3 / 3B search winners | **None passed gates** under broker-correct fills (val PF 1.6, block PF 1.0, trade counts). |
| V53.6 historical PF ~2.3–2.6 | **REPRODUCTION VERIFIED** against internal ledger only; **not** production authorization; independent “executable edge” promotion path closed / not authorized. Frozen methodology preserved as historical research contract. |
| Generation 3 | Explicit **0 qualified** under broker-correct + frozen gates. |

---

## 4. Candidates tested this run

- **No new strategy parameters trained** (data unavailable).
- **Reconciled** Stage 3 near-misses + V53.6 reconstruction + RSI9 invalidation from repository evidence.

---

## 5. Promotion decision (this run)

**NO candidate is ELIGIBLE FOR INTEGRATION PROPOSAL.**  
**NO PROMOTION.**

Final Test remains **LOCKED** for selection (per USDCHF CHECKPOINT).

---

## 6. Next concrete research action (highest leverage)

1. **Restore** `USDCHF_M5_BIDASK_5Y.csv` (and other pair Bid/Ask sets) to a **local/research path outside production**, verify SHA-256 `f93d6440dafb3427f7ceffd0ed9265d7bc02a6434864cba4ce288533d805ff97`.
2. Re-run **independent** broker-correct SHORT/LONG simulators (not only ledger-matched reconstruction) with explicit side rules; publish per-trade file.
3. Only if a candidate passes Stage 3 gates **and** six-block / Final Test protocol without touching Final Test during selection — open an integration **proposal** (separate governance).

Until step 1, further “discovery” claims would be documentation-only.

---

## 7. Governance

- V53.6 frozen methodology **not modified**.
- main **not** merged.
- No production deploy, queue mutation, EA install, or `production_authorized=true`.
