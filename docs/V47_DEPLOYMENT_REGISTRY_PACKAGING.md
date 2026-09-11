# V47 — Registry packaging in Docker (deployment hardening)

## Defect (V46 live)

Render logs showed:

```text
Registry loaded: 2 rulebooks, 1 instruments
```

Root cause: `docker/Dockerfile` copied `backend/`, `release/`, portals, but **not** `registry/v40/*.csv`.  
`RegistryService` resolves `REPO_ROOT/registry/v40` (`/app/registry/v40` in the container). Missing CSVs → founding_registry only.

## Fix

```dockerfile
COPY registry ./registry
COPY governance ./governance
```

After redeploy, expect roughly **6+ CSV rulebooks** merged with founding GBPUSD books, and **multiple instruments** (AUDUSD, USDCHF, NZDUSD, GBPUSD, rejected pairs, etc.).

## Verify live

```bash
curl -sS "$API/api/registry/pairs"
curl -sS "$API/api/registry/rulebooks"
```

Production authorization remains `false` on research candidates (Universal Router).
