"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited
File    : brain_router.py

POST /aegis/analyze — screenshot in, signal out. Records upload diagnostics
(latency, success/failure) for the admin diagnostics views.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.core.upload_config import MAX_UPLOAD_SIZE
from app.security import verify_api_key, require_account_match, AuthContext
from app.core.account_rate_limit import enforce_account_rate_limit

router = APIRouter(tags=["Brain / Vision Analysis"])

_IMAGE_CONTENT_TYPES = (
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/x-ms-bmp",
    "application/octet-stream",
)


@router.post("/aegis/analyze")
async def analyze_screenshot(
    request: Request,
    image: UploadFile = File(...),
    account_id: str = Form(""),
    captured_at_ms: int | None = Form(None),
    symbol: str = Form(""),
    timeframe: str = Form("M5"),
    engine: str = Form(""),  # empty = V40 universal (default); legacy_v3 = old indicator path
    # Observation package (optional numerical layer)
    candle_ts_ms: int | None = Form(None),
    device_ts_ms: int | None = Form(None),
    sequence: int | None = Form(None),
    ohlc_open: str = Form(""),
    ohlc_high: str = Form(""),
    ohlc_low: str = Form(""),
    ohlc_close: str = Form(""),
    ohlc_volume: str = Form(""),
    quote_bid: str = Form(""),
    quote_ask: str = Form(""),
    auth: AuthContext = Depends(verify_api_key),
):
    # Client mobile keys: account is defined by the key, not the form field.
    # This prevents 403 when Account ID in the app is mistyped or stale.
    if not auth.is_admin:
        if not auth.account_id:
            raise HTTPException(
                status_code=403,
                detail="This API key is not bound to an account. Use a mobile key from portal Connect mobile.",
            )
        account_id = auth.account_id
    else:
        require_account_match(auth, account_id)
    await enforce_account_rate_limit(request, account_id)

    brain = request.app.state.brain_cv_service
    job_queue = request.app.state.job_queue
    worker_pool = request.app.state.worker_pool
    history_service = request.app.state.indicator_history
    upload_diag = getattr(request.app.state, "upload_diagnostics", None)

    t0 = time.perf_counter()

    ct = (image.content_type or "").split(";")[0].strip().lower()
    if ct and ct not in _IMAGE_CONTENT_TYPES and not ct.startswith("image/"):
        if upload_diag:
            await upload_diag.record(
                account_id=account_id,
                success=False,
                http_status=400,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error_code="bad_content_type",
                detail=str(image.content_type),
            )
        raise HTTPException(
            status_code=400,
            detail=f"Only image files are accepted (got content-type={image.content_type!r}).",
        )

    image_bytes = await image.read()

    if not image_bytes:
        if upload_diag:
            await upload_diag.record(
                account_id=account_id,
                success=False,
                http_status=400,
                latency_ms=(time.perf_counter() - t0) * 1000,
                error_code="empty_body",
            )
        raise HTTPException(status_code=400, detail="Empty image body.")

    if len(image_bytes) > MAX_UPLOAD_SIZE:
        if upload_diag:
            await upload_diag.record(
                account_id=account_id,
                success=False,
                http_status=413,
                latency_ms=(time.perf_counter() - t0) * 1000,
                image_bytes=len(image_bytes),
                error_code="too_large",
            )
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({len(image_bytes)} bytes). Max is {MAX_UPLOAD_SIZE} bytes.",
        )

    from app.services.observation_package import (
        build_ohlc_from_form,
        validate_observation,
        floor_to_m5_ms,
        next_m5_boundary_ms,
    )
    client_ohlc = build_ohlc_from_form(
        open_=ohlc_open or None,
        high=ohlc_high or None,
        low=ohlc_low or None,
        close=ohlc_close or None,
        volume=ohlc_volume or None,
        bid=quote_bid or None,
        ask=quote_ask or None,
        candle_ts_ms=candle_ts_ms or captured_at_ms,
    )
    obs_device_ts = device_ts_ms or captured_at_ms
    obs_candle_ts = candle_ts_ms or (floor_to_m5_ms(int(captured_at_ms)) if captured_at_ms else None)

    try:
        cv_image = brain.decode_image(image_bytes)
        frame_state = brain.extract_frame_state(cv_image)

        # Synchronization layer: use the MT5 terminal already connected by the
        # account's Windows worker. No external broker market-data API is used.
        market_snapshot = None
        pair_artifact = None
        # Optional MT5 OHLC sync — never fail the screenshot upload if worker is down
        if symbol.strip() and await worker_pool.is_running(account_id):
            try:
                if captured_at_ms is not None:
                    snapshot_job = await job_queue.submit_and_wait(
                        account_id,
                        "get_m1_ohlc_at",
                        {"symbol": symbol.strip(), "captured_at_ms": int(captured_at_ms)},
                        timeout_seconds=10,
                    )
                    if snapshot_job and snapshot_job.get("success"):
                        market_snapshot = snapshot_job.get("result")
                        if isinstance(market_snapshot, dict) and "close" in market_snapshot:
                            frame_state["market_ohlc"] = market_snapshot
                            try:
                                frame_state["price_close"] = float(market_snapshot["close"])
                            except (TypeError, ValueError):
                                pass
            except Exception as snap_exc:
                brain.logger.warning("MT5 snapshot soft-fail for %s: %s", account_id, snap_exc)

        await history_service.append_frame(account_id, frame_state, captured_at_ms)
        history = await history_service.get_history(account_id)

        # --- V47: Universal Router is the primary analysis path ---
        # V3 indicator engine is legacy only (engine=legacy_v3).
        engine_mode = (engine or "").strip().lower()
        if engine_mode in ("legacy_v3", "v3", "indicator_v3"):
            result = brain.evaluate(history)
            result["analysis_path"] = "legacy_v3"
        else:
            from app.services.universal_analysis_service import UniversalAnalysisService
            uni = UniversalAnalysisService()
            effective_snapshot = market_snapshot if isinstance(market_snapshot, dict) else client_ohlc
            result = uni.analyze(
                instrument=symbol.strip(),
                timeframe=(timeframe or "M5").strip() or "M5",
                market_snapshot=effective_snapshot,
                frame_state=frame_state,
            )
            obs_flags = validate_observation(
                instrument=symbol.strip(),
                timeframe=(timeframe or "M5").strip() or "M5",
                screenshot_bytes=image_bytes,
                ohlc=effective_snapshot if isinstance(effective_snapshot, dict) else None,
                device_ts_ms=obs_device_ts,
                candle_ts_ms=obs_candle_ts,
            )
            result["observation"] = {
                **obs_flags,
                "sequence": sequence,
                "candle_ts_ms": obs_candle_ts,
                "device_ts_ms": obs_device_ts,
                "ohlc_source": (
                    "mt5_worker" if isinstance(market_snapshot, dict) else
                    ("client" if client_ohlc else None)
                ),
            }
            result["next_capture_at_ms"] = next_m5_boundary_ms()

            # Attach lightweight frame diagnostics without forcing V3 rules
            if frame_state.get("price_close") is not None:
                result.setdefault("price_close_px", frame_state.get("price_close"))

        if market_snapshot is not None and captured_at_ms is not None:
            from app.services.capture_pair_service import CapturePairService
            # Store a PNG artifact regardless of upload transport format.
            import io
            from PIL import Image
            with io.BytesIO() as buf:
                Image.open(io.BytesIO(image_bytes)).convert("RGB").save(buf, format="PNG")
                png_bytes = buf.getvalue()
            pair_artifact = CapturePairService().save(
                png_bytes, account_id, symbol.strip(), int(captured_at_ms), market_snapshot
            )
    except ValueError as exc:
        if upload_diag:
            await upload_diag.record(
                account_id=account_id,
                success=False,
                http_status=400,
                latency_ms=(time.perf_counter() - t0) * 1000,
                image_bytes=len(image_bytes),
                error_code="decode_or_value",
                detail=str(exc)[:300],
            )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        if upload_diag:
            await upload_diag.record(
                account_id=account_id,
                success=False,
                http_status=500,
                latency_ms=(time.perf_counter() - t0) * 1000,
                image_bytes=len(image_bytes),
                error_code="analysis_failed",
            )
        brain.logger.exception("Screenshot analysis failed for account %s", account_id)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {type(exc).__name__}: {exc}",
        ) from exc

    latency_ms = (time.perf_counter() - t0) * 1000
    if upload_diag:
        await upload_diag.record(
            account_id=account_id,
            success=True,
            http_status=200,
            latency_ms=latency_ms,
            image_bytes=len(image_bytes),
        )

    signal_history = request.app.state.signal_history
    await signal_history.record(
        account_id, result["signal"], result["confidence"], result["rule_name"], result["details"]
    )

    if market_snapshot is not None:
        result["market_data"] = market_snapshot
        result["market_data_source"] = "MT5_TERMINAL_TICKS"
        result["market_data_synchronized"] = True
        result["capture_pair"] = pair_artifact

        # SERVER-SIDE AUTONOMOUS V3 DEMO EXECUTION.
        # This is the missing link in the previous checkpoint: a signal was
        # returned to the mobile app, but nothing called /api/trading/market-order.
        # Execute through the existing account-specific Windows MT5 worker.
        if str(result.get("signal") or "HOLD").upper() in ("BUY", "SELL"):
            try:
                from app.services.autonomous_execution_service import AutonomousDemoExecutionService
                auto = AutonomousDemoExecutionService(
                    job_queue=job_queue,
                    worker_pool=worker_pool,
                    subscription_service=request.app.state.subscription_service,
                    trade_limits=getattr(request.app.state, "trade_limits", None),
                )
                vault = getattr(request.app.state, "vault", None)
                if vault is not None:
                    auto.credential_getter = vault.get_credentials_by_account
                execution = await auto.execute_if_signal(
                    account_id=account_id,
                    symbol=symbol.strip(),
                    result=result,
                    market_snapshot=market_snapshot,
                )
                result["execution"] = execution
            except Exception as exc:
                brain.logger.exception("Autonomous demo execution integration failed for account %s", account_id)
                result["execution"] = {"status": "integration_error", "executed": False, "message": str(exc)}
    else:
        result["market_data_synchronized"] = False
    result["timestamp"] = int(time.time() * 1000)
    result["latency_ms"] = round(latency_ms, 1)
    return result
