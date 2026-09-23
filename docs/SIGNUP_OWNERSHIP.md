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
