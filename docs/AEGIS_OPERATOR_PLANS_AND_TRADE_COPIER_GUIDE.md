# AEGIS Operator Guide — Subscription Plans & Trade Copier Grants

**Audience:** Operator / admin (including Neon SQL Editor users)  
**Branch:** `stage-6.6-operational-integrity`  
**API base URL:** `https://aegis-api-0z1p.onrender.com`  
**Last updated:** 2026-10-14  

**Safety**

- Prefer the **admin API (curl)** when possible; it sets plan limits consistently.
- In Neon, always use the **production** branch. Never run grants on a temporary recovery branch.
- Do **not** paste API keys into chat, screenshots, or public tickets.
- Granting a commercial plan is **not** the same as `production_authorized=true` for strategy execution. Execution safety gates remain separate.

---

## 1. Plan catalogue (source of truth)

| Plan code | Devices (`max_devices`) | Trades / day (`max_trades_per_day`) | Notes |
|-----------|-------------------------|--------------------------------------|--------|
| `demo` | 1 | 100 (catalog) | Free trial style; not paid checkout |
| `starter` | 1 | 15 | Paid tier |
| `pro` | 1 | 50 | Paid tier |
| `business` | 3 | 200 | Paid tier |
| `enterprise` | 10 | **0 = unlimited** | Manual / sales-assisted |

Table: `subscriptions`  
Primary key: `account_id` (example: `ACC-1987D3D2E6`)

Important:

- **`max_trades_per_day = 0` means unlimited**, not “zero trades allowed”.
- Access is driven mainly by **`status = 'active'`** (or `past_due` inside grace).  
- Admin **`POST /api/admin/tenants/set-plan` does not set an automatic expiry** in months. A curl-granted plan stays usable until you change `status` (or a billing webhook does).

---

## 2. Grant a plan without a paid subscription (recommended: curl)

Use an **admin API key** in the header `X-API-Key`.

```bash
curl -sS -X POST 'https://aegis-api-0z1p.onrender.com/api/admin/tenants/set-plan' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_ADMIN_API_KEY' \
  -d '{"account_id":"ACC-1987D3D2E6","plan":"enterprise","status":"active"}'
```

Replace:

- `YOUR_ADMIN_API_KEY` — admin key only  
- `ACC-1987D3D2E6` — target account  
- `"enterprise"` — any of: `demo`, `starter`, `pro`, `business`, `enterprise`

Expected behaviour:

- Creates a `subscriptions` row if missing (`provider=manual`).
- Updates `plan`, `max_devices`, `max_trades_per_day`, `status`, `updated_at`.
- Does **not** require Stripe/Paystack payment.

### How long does a curl grant last?

**No fixed number of months** from the set-plan endpoint alone.

| Mechanism | Effect |
|-----------|--------|
| `status = 'active'` | Account is treated as active by `is_active()` |
| `current_period_end` | Stored for billing/display; **not** what currently turns access off by itself in `is_active()` |
| To end access | Set `status` to `canceled` (or non-active), or use provider cancel + webhook |

Optional: set a calendar end date in Neon for your own records (see SQL below). That date alone does not auto-disable the plan unless you later change status or add automation.

---

## 3. Grant a plan in Neon (SQL)

### Common mistake

Pasting only:

```sql
SET plan = 'enterprise', ...
WHERE account_id = 'ACC-1987D3D2E6';
```

**fails** because PostgreSQL needs a full statement: **`UPDATE subscriptions SET ...`**.

### Update existing row

```sql
UPDATE subscriptions
SET
  plan = 'enterprise',
  status = 'active',
  max_devices = 10,
  max_trades_per_day = 0,
  current_period_end = '2030-12-31 23:59:59+00',
  grace_period_ends_at = NULL,
  trading_halted = FALSE,
  halted_reason = NULL,
  provider = 'manual',
  updated_at = NOW()
WHERE account_id = 'ACC-1987D3D2E6';
```

### Insert if no row exists

If `UPDATE` changes 0 rows, insert (adjust if your schema has extra NOT NULL columns without defaults):

```sql
INSERT INTO subscriptions (
  account_id, plan, status, max_devices, max_trades_per_day,
  current_period_end, grace_period_ends_at, trading_halted, halted_reason,
  provider, risk_preset, risk_tolerance_pct, trading_mode,
  account_type, account_currency, open_risk_usd, updated_at
) VALUES (
  'ACC-1987D3D2E6', 'enterprise', 'active', 10, 0,
  '2030-12-31 23:59:59+00', NULL, FALSE, NULL,
  'manual', 'standard', 25.0, 'multi_symbol',
  'standard', 'USD', 0, NOW()
);
```

If insert errors, list columns:

```sql
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'subscriptions'
ORDER BY ordinal_position;
```

### Verify plan

```sql
SELECT account_id, plan, status, max_devices, max_trades_per_day,
       current_period_end, provider, trading_halted, updated_at
FROM subscriptions
WHERE account_id = 'ACC-1987D3D2E6';
```

### Revoke plan access

```sql
UPDATE subscriptions
SET status = 'canceled', updated_at = NOW()
WHERE account_id = 'ACC-1987D3D2E6';
```

---

## 4. Trade Copier — grant without a paid “copier subscription” product

Trade Copier is an **add-on table**, not a row in `subscriptions`.

| Table | Role |
|-------|------|
| `subscriptions` | Base AEGIS plan (required first) |
| `trade_copier_addons` | Copier tier for the **master** account |
| `trade_copier_slaves` | Slave MT5 targets |

**Code rule:** activating the copier requires a base subscription with  
`status IN ('active', 'past_due', 'demo')`.  
You cannot activate the copier with **no** subscription row. A **demo** or **manual enterprise** base plan is enough for setup; you do **not** need a separate paid Stripe copier product if you grant via API or SQL.

### Copier tiers

| Tier code | Max slaves |
|-----------|------------|
| `copier_3` | 3 |
| `copier_10` | 10 |
| `copier_25` | 25 |

### Step A — Ensure base plan (curl or Neon)

Use Section 2 or 3 so the account is `active` (any plan including `demo` or `enterprise`).

### Step B — Activate copier (API)

```bash
curl -sS -X POST 'https://aegis-api-0z1p.onrender.com/api/copier/activate' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_API_KEY_FOR_THAT_ACCOUNT' \
  -d '{"account_id":"ACC-1987D3D2E6","tier":"copier_3"}'
```

Use a key allowed for that `account_id` (account match rules apply).

### Step B (alternative) — Activate copier in Neon

```sql
INSERT INTO trade_copier_addons (account_id, tier, status, max_slaves, updated_at)
VALUES ('ACC-1987D3D2E6', 'copier_3', 'active', 3, NOW())
ON CONFLICT (account_id) DO UPDATE SET
  tier = EXCLUDED.tier,
  status = 'active',
  max_slaves = EXCLUDED.max_slaves,
  updated_at = NOW();
```

For `copier_10` use `max_slaves = 10`; for `copier_25` use `25`.

### Step C — Add a slave (API)

```bash
curl -sS -X POST 'https://aegis-api-0z1p.onrender.com/api/copier/slaves' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_API_KEY' \
  -d '{
    "account_id": "ACC-1987D3D2E6",
    "label": "Slave-1",
    "server": "Broker-Server-Name",
    "login": "12345678",
    "broker_name": "Broker",
    "risk_mode": "multiplier",
    "risk_value": 1.0
  }'
```

If the API returns a field error, adjust body to match the live schema (response message is authoritative).

### Verify copier

```sql
SELECT * FROM trade_copier_addons WHERE account_id = 'ACC-1987D3D2E6';

SELECT id, label, server, login, enabled, risk_mode, risk_value
FROM trade_copier_slaves
WHERE master_account_id = 'ACC-1987D3D2E6';
```

### Disable copier

```sql
UPDATE trade_copier_addons
SET status = 'canceled', updated_at = NOW()
WHERE account_id = 'ACC-1987D3D2E6';
```

(Or set slaves `enabled = false`.)

---

## 5. Operator checklist

**Grant trading plan (manual / unpaid)**

1. [ ] Admin API key ready (not shared in chat)  
2. [ ] Account ID known (`ACC-…`)  
3. [ ] `POST /api/admin/tenants/set-plan` **or** full `UPDATE subscriptions …`  
4. [ ] Verify SELECT on `subscriptions`  
5. [ ] Remember: curl grant does not auto-expire monthly  

**Grant Trade Copier**

1. [ ] Base plan `status` is `active` (or demo / past_due)  
2. [ ] `POST /api/copier/activate` **or** upsert `trade_copier_addons`  
3. [ ] Add slaves via API or insert into `trade_copier_slaves`  
4. [ ] Verify addon + slaves  

**Do not confuse with**

- [ ] Strategy `production_authorized` (separate; remain false unless explicitly authorized)  
- [ ] Controlled-demo execution signals  
- [ ] MT5 EA install / OrderSend  

---

## 6. Related docs in this repository

| Doc | Topic |
|-----|--------|
| `docs/COMMERCIAL_PLANS.md` | Short plan table + set-plan pointer |
| This file | Full operator procedures for Neon + curl + copier |
| `docs/AEGIS_STAGE_6_6_STATUS_AND_OPERATOR_EVIDENCE_PACKAGE.md` | Stage 6.6 evidence package |

---

## 7. Where to get this guide (Markdown vs PDF)

| Format | Location |
|--------|----------|
| **Markdown (always current on this branch)** | GitHub → branch `stage-6.6-operational-integrity` → `docs/AEGIS_OPERATOR_PLANS_AND_TRADE_COPIER_GUIDE.md` |
| **Direct GitHub URL (after push)** | `https://github.com/honeydewnuts-pixel/AEGIS_Platform_Server/blob/stage-6.6-operational-integrity/docs/AEGIS_OPERATOR_PLANS_AND_TRADE_COPIER_GUIDE.md` |
| **PDF** | See `docs/AEGIS_OPERATOR_PLANS_AND_TRADE_COPIER_GUIDE.pdf` on the **same branch** when present. **Not** served from the public marketing website download gate (that path is for the mobile APK / subscriber download). |

Open the Markdown on GitHub → use the browser **Print → Save as PDF** if you need a PDF immediately and the committed PDF is not yet available.
