# AEGIS Project Status — 2026-09-28

## Research
USDCHF is the active instrument. The current task is V53.6 cash-test reconciliation and completion of the requested cash-test programme. The research datasets and outputs in this package are separate from the operational Server and have not automatically been integrated.

## Server
The existing Server contains the older V53.6 operational implementation according to the project checkpoint. The latest Server archive available in the working files is reported as commit `9eb0fc2085ad61c568f416901121fa9ad8d5f7ee`; a later Builder-reported commit may exist. The Builder must inspect the live GitHub HEAD before making changes. No claim is made that the VPS runtime is currently healthy or faulty.

## Preservation rules
1. Preserve original datasets and outputs; never silently overwrite results.
2. Distinguish exploratory, reconstructed, reproduced, validated, approved, integrated, and server-verified work.
3. Keep Final Test locked for selection/qualification.
4. Every major milestone gets a durable checkpoint and versioned commit.
5. Server integration requires a specification, commit reference, and implementation/regression-test evidence.
6. Do not commit secrets, API keys, account credentials, or private customer data.

## Immediate priorities
1. Investigate the VPS/Demo state and check for unintended execution.
2. Commit this research handoff without changing Server runtime code.
3. Reconcile the USDCHF cash artifacts.
4. Continue USDCHF from the preserved stage.
