# V46 Repository Verification

Date: 2026-09-10

- Git working tree: clean
- Git branch: main
- Canonical commit: 556a0f6e2aae3a7954414744bf0d98656c0c2f5c
- V46 Universal Router smoke cases: 3/3 PASS
- Python compile check for V46 router: PASS
- Render Blueprint YAML parse: PASS
- Render service topology: web `aegis-api`, Postgres `aegis-postgres`, Key Value `aegis-redis`
- Production authorization: FALSE
- MT5 live authorization: DEMO_ONLY / disabled
- Full inherited pytest suite: not claimed; this environment lacks `asyncpg` for the inherited test configuration. CI installs requirements-dev and includes asyncpg.
- Render deployment: not claimed as completed; this repository contains the deployment blueprint and Docker configuration for the real deployment step.

## GitHub file-size control
One historical V39 archive exceeds GitHub's 100 MiB per-file limit. It is excluded from the GitHub-ready tree and recorded with SHA-256 in `EXTERNAL_LARGE_ARTIFACTS.md`. It is not a runtime dependency.
