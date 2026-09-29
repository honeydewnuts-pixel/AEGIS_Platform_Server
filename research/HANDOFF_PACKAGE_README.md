# AEGIS Research Handoff — 2026-09-28

This package preserves available USDCHF research artifacts and gives the Builder a safe GitHub-import assignment.

**Boundary:** this is research material, not evidence that the USDCHF research has been integrated into the AEGIS Server. Do not modify Server runtime code during import.

Contents:
- `checkpoint/PROJECT_STATUS.md`
- `checkpoint/USDCHF_CHECKPOINT.md`
- `checkpoint/RESEARCH_CHECKPOINT.yaml`
- `checkpoint/INTEGRATION_REGISTER.csv`
- `checkpoint/DATASET_MANIFEST.csv` and `checkpoint/SHA256SUMS.txt`
- `builder/BUILDER_IMPORT_INSTRUCTIONS.md`
- `artifacts/` with available source data, ledgers, summaries, and mobile screenshots.

Import under a `research/` directory in the existing GitHub repository unless an established research repository already exists. Verify hashes after import. Do not silently omit large files; use Git LFS or an appropriate durable artifact store if needed.
