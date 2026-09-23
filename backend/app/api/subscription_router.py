"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : subscription_router.py
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.security import verify_api_key, require_account_match, require_admin, AuthContext
from app.core.rate_limit import limiter
from app.services.payment_providers.paystack_adapter import PaystackAdapter
from app.services.payment_providers.flutterwave_adapter import FlutterwaveAdapter
from app.services.payment_providers.stripe_adapter import StripeAdapter

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])

ADAPTERS = {
    "paystack": PaystackAdapter,
    "flutterwave": FlutterwaveAdapter,
    "stripe": StripeAdapter,
}


class CheckoutRequest(BaseModel):
    """account_id is ignored for ownership — must match server-issued signup_session."""
    signup_session_id: str = Field(..., description="From POST /api/subscriptions/signup-session")
    email: EmailStr
    plan: str = "starter"
    # Deprecated: client-supplied account_id is no longer trusted
    account_id: str | None = Field(default=None, description="Ignored; bound from signup session")


def get_subscription_service(request: Request):
    return request.app.state.subscription_service


def get_credential_reveal_service(request: Request):
    return request.app.state.credential_reveal


@router.post("/checkout/{provider}")
@limiter.limit("5/minute")
async def create_checkout(
    provider: str,
    checkout_request: CheckoutRequest,
    request: Request,  # required by @limiter.limit - slowapi inspects this for the client IP
    credential_reveal=Depends(get_credential_reveal_service),
):
    """
    Deliberately NOT behind verify_api_key: a brand-new subscriber has no
    AEGIS API key yet (keys are issued on first successful activation -
    see SubscriptionService.apply_event), so there's nothing to check them
    against at this point in the flow. This just creates a payment
    provider checkout session/URL - no AEGIS account data is exposed by
    letting an anonymous caller do that.

    Rate-limited (5/minute per IP) since it's the one endpoint in this
    API with no auth at all - see app/core/rate_limit.py for the shared
    Limiter instance.
    """
    adapter_cls = ADAPTERS.get(provider)
    if adapter_cls is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    # Ownership: only server-issued signup sessions may bind account_id into payment metadata.
    signup_svc = getattr(request.app.state, "signup_sessions", None)
    if signup_svc is None:
        raise HTTPException(status_code=503, detail="Signup session service unavailable")
    sess = await signup_svc.get(checkout_request.signup_session_id)
    if not sess:
        raise HTTPException(status_code=400, detail="Invalid or expired signup_session_id")
    if sess.get("email", "").lower() != str(checkout_request.email).strip().lower():
        raise HTTPException(status_code=400, detail="Email does not match signup session")
    account_id = sess["account_id"]
    # Session is authoritative for plan — never trust client to upgrade tier
    from app.services.plan_catalog import normalize_checkout_plan
    try:
        plan = normalize_checkout_plan(sess.get("plan") or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    client_plan = (checkout_request.plan or "").strip().lower()
    if client_plan:
        try:
            client_norm = normalize_checkout_plan(client_plan)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if client_norm != plan:
            raise HTTPException(
                status_code=400,
                detail="plan does not match signup session",
            )

    # Atomic claim before calling payment provider (prevents concurrent double checkout)
    try:
        await signup_svc.try_begin_checkout(checkout_request.signup_session_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    reveal_token = await credential_reveal.create_reveal_token(account_id)

    adapter = adapter_cls()
    session = await adapter.create_checkout_session(
        account_id, str(checkout_request.email), plan, reveal_token
    )
    await signup_svc.set_payment_reference(
        checkout_request.signup_session_id,
        getattr(session, "reference", None) or "",
    )
    return {
        "checkout_url": session.checkout_url,
        "reference": session.reference,
        "account_id": account_id,
        "plan": plan,
        "signup_session_id": checkout_request.signup_session_id,
        "session_state": "CHECKOUT_CREATED",
    }


@router.post("/webhook/{provider}")
async def receive_webhook(provider: str, request: Request):
    """
    No verify_api_key here either - these are called by the payment
    provider, not your clients. Authenticity is established by the
    provider-specific signature check instead (see each adapter's
    verify_webhook_signature).
    """
    adapter_cls = ADAPTERS.get(provider)
    if adapter_cls is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")

    adapter = adapter_cls()
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if not adapter.verify_webhook_signature(raw_body, headers):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    event = adapter.parse_webhook_event(raw_body)

    subscription_service = request.app.state.subscription_service
    if await subscription_service.already_processed(event.provider, event.provider_event_id):
        return {"status": "already_processed"}

    newly_issued = await subscription_service.apply_event(event)

    if newly_issued is not None:
        # First activation - stage the new credentials so the subscriber's
        # browser can claim them via GET /reveal once it's redirected back
        # from the payment provider (see checkout's reveal_token above).
        credential_reveal = request.app.state.credential_reveal
        await credential_reveal.stash_credentials(
            newly_issued["account_id"], newly_issued["portal_token"], newly_issued["mobile_api_key"]
        )

    # If payment failed or subscription was canceled, immediately try to
    # disconnect any live MT5 worker rather than waiting for the next
    # background sweep cycle.
    if event.account_id and event.event_type.name in ("PAYMENT_FAILED", "SUBSCRIPTION_CANCELED"):
        worker_pool = request.app.state.worker_pool
        if await worker_pool.is_running(event.account_id) and not await subscription_service.is_active(event.account_id):
            await worker_pool.stop_worker(event.account_id)

    return {"status": "processed"}


@router.get("/reveal")
async def reveal_credentials(
    account_id: str,
    reveal_token: str,
    credential_reveal=Depends(get_credential_reveal_service),
):
    """
    One-time claim of a brand-new subscriber's portal_token + mobile API
    key, using the reveal_token embedded in the payment provider's
    success redirect URL (see create_checkout above). Returns 404 if the
    token is wrong, already used, expired, or the webhook hasn't arrived
    yet - client_portal/success.html retries a few times to cover that
    last case, since webhooks can take a few seconds.
    """
    result = await credential_reveal.reveal(account_id, reveal_token)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Not ready yet, or already claimed. If you just paid, wait a few seconds and retry.",
        )
    return result


@router.get("/status/{account_id}")
async def get_subscription_status(
    account_id: str,
    subscription_service=Depends(get_subscription_service),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    record = await subscription_service.get_status(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No subscription found for this account.")
    record["is_active"] = await subscription_service.is_active(account_id)
    return record


@router.get("")
async def list_subscriptions(
    subscription_service=Depends(get_subscription_service),
    auth: AuthContext = Depends(verify_api_key),
):
    """Admin-facing: every subscription, for the admin dashboard."""
    require_admin(auth)
    return await subscription_service.list_all()


@router.post("/{account_id}/cancel")
async def cancel_subscription(
    account_id: str,
    request: Request,
    subscription_service=Depends(get_subscription_service),
    auth: AuthContext = Depends(verify_api_key),
):
    """
    Admin-only for now - previously cancel_subscription() existed on every
    payment adapter but nothing anywhere actually called it, so there was
    no way to cancel a subscription at all. Subscriber self-service
    cancellation (from client_portal) is a reasonable next step but
    deliberately not added here yet, since "can a subscriber cancel their
    own subscription" has billing/refund policy implications worth a
    deliberate decision, not a default.
    """
    require_admin(auth)

    record = await subscription_service.get_status(account_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No subscription found for this account.")

    adapter_cls = ADAPTERS.get(record.get("provider"))
    if adapter_cls is None:
        raise HTTPException(status_code=400, detail=f"Unknown or missing provider on this subscription record: {record.get('provider')}")

    adapter = adapter_cls()
    success = await adapter.cancel_subscription(
        record["provider_subscription_id"], record.get("provider_customer_id")
    )
    if not success:
        raise HTTPException(status_code=502, detail="Payment provider did not confirm cancellation - check server logs for the specific reason.")

    await subscription_service.mark_canceled(account_id)  # local status update; the provider's own webhook will also arrive and confirm independently

    worker_pool = request.app.state.worker_pool
    if await worker_pool.is_running(account_id):
        await worker_pool.stop_worker(account_id)

    return {"status": "canceled", "account_id": account_id}


import uuid


class DemoSignupRequest(BaseModel):
    email: EmailStr = Field(..., description="Required — establishes signup identity")
    # Client-supplied account_id is rejected for SaaS ownership safety
    account_id: str | None = Field(default=None, description="Ignored; always server-generated")


class SignupSessionRequest(BaseModel):
    email: EmailStr
    plan: str = "monthly"
    purpose: str = Field(default="checkout", description="demo|checkout")


@router.post("/signup-session")
@limiter.limit("10/minute")
async def create_signup_session(body: SignupSessionRequest, request: Request):
    """Issue a short-lived server-bound account identity before checkout or demo."""
    svc = getattr(request.app.state, "signup_sessions", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="Signup session service unavailable")
    purpose = (body.purpose or "checkout").strip().lower()
    if purpose not in ("demo", "checkout"):
        purpose = "checkout"
    try:
        payload = await svc.create(email=str(body.email), plan=body.plan, purpose=purpose)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "signup_session_id": payload["session_id"],
        "account_id": payload["account_id"],
        "email": payload["email"],
        "plan": payload["plan"],
        "expires_in_sec": 3600,
        "note": "Use signup_session_id for checkout; account_id is server-bound to this session.",
    }


@router.post("/demo/signup")
@limiter.limit("5/minute")
async def demo_signup(body: DemoSignupRequest, request: Request):
    """
    Public endpoint: create a NEW 14-day demo plan only.
    Account ID is always server-generated. Existing accounts cannot be taken over.
    """
    signup_svc = getattr(request.app.state, "signup_sessions", None)
    email = str(body.email).strip().lower()
    if signup_svc is not None:
        sess = await signup_svc.create(email=email, plan="demo", purpose="demo")
        account_id = sess["account_id"]
    else:
        account_id = f"DEMO-{uuid.uuid4().hex[:10].upper()}"

    sub = request.app.state.subscription_service
    try:
        issued = await sub.activate_demo(
            account_id, contact_email=email, allow_refresh_existing=False
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Demo activation failed: {type(e).__name__}: {e}",
        ) from e

    # Download token is optional — never fail the whole signup if APK token table errors
    download_url = None
    download_token = None
    try:
        bindings = getattr(request.app.state, "device_bindings", None)
        if bindings is not None:
            download_token = await bindings.issue_download_token(
                account_id=account_id, plan="demo", max_uses=1, ttl_hours=72
            )
            base = str(request.base_url).rstrip("/")
            download_url = f"{base}/api/download/apk?token={download_token}"
    except Exception:
        download_url = "https://www.leveragefx.co/downloads/aegis-mobile.apk?v=1.9.0"

    try:
        audit = getattr(request.app.state, "audit_service", None)
        if audit is not None:
            await audit.record(
                action="subscription.demo_signup",
                actor_type="system",
                account_id=account_id,
                detail="demo plan activated",
                ip=request.client.host if request.client else None,
            )
    except Exception:
        pass

    # Always ensure a mobile key is present for first-time demo users
    if not issued.get("mobile_api_key"):
        try:
            from app.security import issue_api_key
            issued["mobile_api_key"] = await issue_api_key(
                account_id=account_id,
                is_admin=False,
                label=f"demo mobile key for {account_id}",
                issued_by="demo_signup_ensure",
            )
            issued["key_reused"] = False
            issued["note"] = "Copy mobile_api_key into the app with this account_id."
        except Exception as e:
            issued["key_error"] = f"{type(e).__name__}: {e}"

    return {
        **issued,
        "download_url": download_url,
        "download_token": download_token,
        "limits": {
            "brain_analysis": True,
            "live_trading": False,
            "device_binding": True,
            "demo_days": 14,
        },
    }



class RiskPresetRequest(BaseModel):
    account_id: str
    risk_preset: str


@router.post("/risk_preset")
async def set_risk_preset(
    body: RiskPresetRequest,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    """Set risk preset for an account. Server calculates and returns final lot size."""
    require_account_match(auth, body.account_id)
    sub = request.app.state.subscription_service
    try:
        result = await sub.set_risk_preset(body.account_id, body.risk_preset)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid risk_preset")
    return result


@router.get("/risk_preset/{account_id}")
async def get_risk_preset(
    account_id: str,
    request: Request,
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)
    sub = request.app.state.subscription_service
    record = await sub.get_status(account_id)
    if not record:
        raise HTTPException(status_code=404, detail="No subscription found for this account.")
    return {
        "status": "success",
        "risk_preset": record.get("risk_preset", "standard"),
        "calculated_lot_size": record.get("calculated_lot_size"),
        "plan_max_lot": record.get("plan_max_lot"),
        "plan_base_lot": record.get("plan_base_lot"),
    }
