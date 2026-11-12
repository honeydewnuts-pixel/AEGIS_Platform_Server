# AEGIS Repository Rehabilitation (reconciled)

**Branch:** research/repository-rehabilitation-20261112b  
**Based on main:** f546af71b88b250f7a30d6614d74b6d818505177  

**production_authorized=false**  
**execution_authorized=false**

## Why the prior branch diverged

Commit ad09143 was parented on local commit 493482a (older line), not on origin/main f546af7.
GitHub therefore reported the rehab branch as behind main by dozens of commits and the comparison showed mass deletions of files that simply were not in the sparse/orphan parent history.

This branch is created with **parent = origin/main** so the only diffs are intentional rehabilitation changes.

## Changes

- Empty operational rulebook/instrument registries
- founding_registry() empty
- No instrument derivation from rulebook rows
- activate() and get_active_pointer() fail closed
- Tests extended for activation rejection and stale profile
