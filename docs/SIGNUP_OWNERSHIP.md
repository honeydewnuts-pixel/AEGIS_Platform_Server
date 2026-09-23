# Signup & checkout ownership (commercial SaaS)

## Demo

```http
POST /api/subscriptions/demo/signup
{ "email": "user@example.com" }
```

- Server generates `DEMO-…` account ID.
- Client `account_id` is **ignored**.
- Existing accounts **cannot** be reactivated via this public endpoint.

## Paid checkout

```http
POST /api/subscriptions/signup-session
{ "email": "user@example.com", "plan": "monthly", "purpose": "checkout" }
→ { signup_session_id, account_id, … }

POST /api/subscriptions/checkout/paystack
{ "signup_session_id": "…", "email": "user@example.com", "plan": "monthly" }
```

Payment metadata uses the **session-bound** `account_id` only.


## Checkout plan binding (SaaS)

- `signup_session.plan` is authoritative; client-supplied plan must match or is ignored with 400.
- Unknown plans are rejected at the payment boundary (no silent fallback to Starter).
- Checkout claim is atomic (`CREATED` → `CHECKOUT_CREATED`) before calling the payment provider.
