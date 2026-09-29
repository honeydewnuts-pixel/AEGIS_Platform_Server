# Builder Assignment — Preserve AEGIS Research in GitHub

## Goal
Import this handoff package into the user's GitHub repository as a durable research checkpoint. This is a repository-preservation task, not a Server feature change.

## Procedure
1. Inspect the live repository, branch, working tree, current HEAD, and existing research folders before editing.
2. If an established research repository exists, use it. Otherwise, add a top-level `research/` directory in the existing repository. Do not create a duplicate structure without explaining why.
3. Preserve all existing Server source and deployment files. Do not change runtime behavior in this task.
4. Import the package's `checkpoint/` files and all `artifacts/` files. Keep originals unchanged. A sensible destination is `research/instruments/USDCHF/` plus `research/checkpoint/`.
5. Verify imported artifacts against `checkpoint/DATASET_MANIFEST.csv` and `checkpoint/SHA256SUMS.txt`.
6. For large CSVs, use Git LFS or a durable versioned artifact store if needed. Do not silently omit any file. If a file cannot be stored, commit the checkpoint/manifests and report the exact blocked file and a durable next step.
7. Add a repository-level research README describing the separation between research and Server code.
8. Maintain the integration register and changelog for future milestones.
9. Commit and push. Do not report success until the remote push is confirmed.

## Constraints
- USDCHF remains active; do not switch instruments.
- The V53.6 reference is short-only, next-bar Ask entry, Bid exits, ATR(14), 1.5 ATR stop, BE at +1R, 0.75 ATR trail, 72-bar maximum, embedded Bid/Ask cost. Do not add universal fixed 0.085R or double-count spread.
- Cash matrix: 7 balances × 7 risks × 3 leverage settings = 147 scenarios; periods are 1 day, 1 week, 1 month, 6 months, 1 year, 5 years.
- Original cash ledger covers only $500/$1,000/$5,000/$10,000 across seven risks. Small-account file is summary-only. Cap-sensitivity differs from original at high risks.
- Final Test stays locked for selection/qualification.
- VPS/Demo issue is unresolved; screenshots do not prove a fault or an executed order. Investigate it separately using MT5 history and backend/feed/analysis/executor/notification logs.
- Latest archive commit noted in package may be stale; inspect live GitHub HEAD.

## Required completion report
Return repository and branch, starting HEAD, resulting commit hash, exact paths, artifact count and hash-verification result, omitted/blocked files, and confirmation that Server runtime source/configuration was not modified.
