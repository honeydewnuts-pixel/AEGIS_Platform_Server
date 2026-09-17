# V53.6 Qualified Rulebook Handoff (integrated)

Source package: `AEGIS_V53_6_QUALIFIED_RULEBOOK_REPOSITORY_HANDOFF.zip`

## Runtime
- Instrument + rulebook CSVs: `registry/v40/` (includes V53.6 eligible IDs)
- Artifact detail: `registry/v53_6/`

## Clients
Android, Windows, and macOS load pairs via `GET /api/registry/pairs` — no hard-coded indicator templates.
After deploy, research-eligible pairs expand to the V53.6 set (still not production-authorized).
