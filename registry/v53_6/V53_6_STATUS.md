# V53.6 Status

- Checkpoint: **V53.6**
- Ten target instruments: V31 transfer **PASS** as `QUALIFIED_RESEARCH_CANDIDATE`
- **production_authorized = false** for all V53.6 books
- GBPUSD V31/V35 remain **SOURCE_RULEBOOK_FROZEN**
- V35 target transfers: **not** included
- Runtime routing still uses `registry/v40/*.csv` (updated to reference V53.6 IDs)
- Per-instrument JSON under `registry/v53_6/<PAIR>/` (7 of 10 folders present in handoff; EURGBP, GBPJPY, NZDCHF metrics in CSV only)
- Router must fail closed when no qualified rulebook exists
