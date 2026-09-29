# AEGIS Research Directory

This directory is the **permanent, version-controlled research record** for AEGIS.

It is **not** the operational trading Server. Importing files here does **not**
change live rulebooks, signal generation, position sizing, margin checks, the
MT5 Feed, or the Executor.

## Why this exists

- Preserve discovery, cash-test, and validation work across conversations and Builders.
- Avoid repeating completed stages or losing methodology.
- Separate **research evidence** from **Server implementation**.
- Track which results have (and have not) been integrated into the Server.

## Layout

| Path | Purpose |
|------|---------|
| `checkpoint/` | Machine-readable checkpoint, manifests, SHA-256 sums, integration register |
| `instruments/<PAIR>/` | Per-instrument checkpoint, artifacts, cash tests, incidents |
| `datasets/` | Dataset manifest (canonical files live under instruments) |
| `methodology/` | Standing research policies (e.g. Final Test lock) |
| `server_integration/` | Research→Server register and Builder change requests |
| `reports/` | Narrative reports when written |
| `v43/` | Pre-existing V43 neural research materials (preserved) |

## Active research stage

See `PROJECT_STATUS.md` and `checkpoint/RESEARCH_CHECKPOINT.yaml`.

**Active instrument:** USDCHF M5 (open cash-test reconciliation).

**Execution reference (research only — do not alter by import):**

- Short-only; next-bar Ask entry; Bid-side exits  
- ATR(14); initial stop 1.5 ATR; BE at +1R; trail 0.75 ATR; max hold 72 bars  
- Bid/Ask costs in prices; **no** universal fixed 0.085R operational cost  

## Validated vs experimental

- **Verified import:** hashes in `checkpoint/SHA256SUMS.txt` match files under `instruments/USDCHF/artifacts/` (and incident screenshots).
- **Not validated by this import:** full 147-scenario cash-test programme; Server runtime health; VPS/Demo incident root cause.
- **Final Test:** locked — see `methodology/FINAL_TEST_LOCK_POLICY.md`.

## Server integration status

See `checkpoint/INTEGRATION_REGISTER.csv` and `server_integration/INTEGRATION_REGISTER.csv`.

No USDCHF research feature is marked integrated or Server-verified solely because it lives in GitHub.

## Process for future milestones

1. Complete the research step and keep exact data, scripts, config, and outputs.  
2. Update checkpoint YAML / instrument CHECKPOINT.md.  
3. Record hashes for new artifacts.  
4. Commit and push under `research/`.  
5. If proposing Server work, update the integration register and add a Builder request under `server_integration/BUILDER_CHANGE_REQUESTS/`.  
6. After Server implementation, record Server commit + test evidence in the register — never mark integrated without evidence.

## Operational Server code

Runtime application code remains under `backend/`, `mobile_app/`, `windows-desktop/`, etc.  
Do not treat `research/` as a deployable package.
