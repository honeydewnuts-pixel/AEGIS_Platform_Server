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
        derive_acquisition_state,
        confidence_presentation,
        derive_hold_reason,
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
        ohlc_missing_reason = None
        worker_connected = False
        # Optional MT5 OHLC sync — never fail the screenshot upload if worker is down
        if not symbol.strip():
            ohlc_missing_reason = "No symbol in observation; set Trade pair in Settings (e.g. GBPUSD)."
        else:
            try:
                worker_connected = bool(await worker_pool.is_running(account_id))
            except Exception:
                worker_connected = False
            if not worker_connected:
                ohlc_missing_reason = (
                    "MT5 worker not connected for this account. "
                    "Link Windows/desktop MT5 worker (MT5 LINK) so the server can read OHLC ticks."
                )
            else:
                try:
                    ts = int(captured_at_ms) if captured_at_ms is not None else int(__import__("time").time() * 1000)
                    snapshot_job = await job_queue.submit_and_wait(
                        account_id,
                        "get_m1_ohlc_at",
                        {"symbol": symbol.strip(), "captured_at_ms": ts},
                        timeout_seconds=12,
                    )
                    if snapshot_job and snapshot_job.get("success"):
                        market_snapshot = snapshot_job.get("result")
                        if isinstance(market_snapshot, dict) and "close" in market_snapshot:
                            frame_state["market_ohlc"] = market_snapshot
                            try:
                                frame_state["price_close"] = float(market_snapshot["close"])
                            except (TypeError, ValueError):
                                pass
                            ohlc_missing_reason = None
                        else:
                            ohlc_missing_reason = "Worker returned success but OHLC payload missing close."
                    else:
                        msg = None
                        if isinstance(snapshot_job, dict):
                            msg = snapshot_job.get("message") or snapshot_job.get("error")
                        ohlc_missing_reason = msg or "MT5 OHLC job failed or timed out."
                except Exception as snap_exc:
                    brain.logger.warning("MT5 snapshot soft-fail for %s: %s", account_id, snap_exc)
                    ohlc_missing_reason = f"MT5 snapshot error: {snap_exc}"

        # Independent OHLC stream (MT5 EA / continuous worker) — preferred over one-shot job
        ohlc_stream = getattr(request.app.state, "ohlc_stream", None)
        stream_payload = None
        if ohlc_stream is not None and symbol.strip():
            stream_payload = ohlc_stream.get(account_id, symbol.strip(), (timeframe or "M5").strip() or "M5")
            if stream_payload and not stream_payload.get("stale"):
                market_snapshot = {
                    "open": stream_payload.get("open"),
                    "high": stream_payload.get("high"),
                    "low": stream_payload.get("low"),
                    "close": stream_payload.get("close"),
                    "bars": stream_payload.get("bars"),
                    "bar_count": stream_payload.get("bar_count"),
                    "source": stream_payload.get("source"),
                    "received_at_ms": stream_payload.get("received_at_ms"),
                    "closed_bar": stream_payload.get("closed_bar"),
                    "current_bar": stream_payload.get("current_bar"),
                }
                frame_state["market_ohlc"] = market_snapshot
                try:
                    frame_state["price_close"] = float(market_snapshot["close"])
                except (TypeError, ValueError):
                    pass
                ohlc_missing_reason = None
                worker_connected = True  # stream implies MT5 data path alive
            elif stream_payload and stream_payload.get("stale"):
                ohlc_missing_reason = ohlc_missing_reason or (
                    f"OHLC stream stale (age_ms={stream_payload.get('age_ms')}). "
                    "MT5 EA should POST /api/mt5/ohlc/stream on each new M5 bar."
                )

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
            acq = derive_acquisition_state(
                obs_flags={
                    **obs_flags,
                    "candle_ts_ms": obs_candle_ts,
                },
                router_state=result.get("router_state"),
                rule_name=result.get("rule_name"),
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
                **acq,
            }
            result["acquisition_state"] = acq["acquisition_state"]
            result["next_capture_at_ms"] = next_m5_boundary_ms()
            # Keep legacy rule_name; surface clearer details for OHLC wait
            if acq["acquisition_state"] == "WAITING_FOR_OHLC" and result.get("rule_name") == "v40_research_awaiting_ohlc":
                result["details"] = acq["summary"] + " " + (result.get("details") or "")
            conf = confidence_presentation(
                acquisition_state=result.get("acquisition_state"),
                router_state=result.get("router_state"),
                rule_name=result.get("rule_name"),
                confidence=result.get("confidence"),
            )
            result.update(conf)
            hold = derive_hold_reason(
                acquisition_state=result.get("acquisition_state"),
                router_state=result.get("router_state"),
                rule_name=result.get("rule_name"),
                signal=result.get("signal"),
                confidence_available=result.get("confidence_available"),
                confidence=result.get("confidence"),
                ohlc_missing_reason=ohlc_missing_reason,
            )
            result.update(hold)
            result["worker_connected"] = worker_connected
            # Server-side features from OHLC history (never from screenshot pixels)
            try:
                from app.services.feature_engine import compute_features
                bars = None
                if isinstance(effective_snapshot, dict):
                    bars = effective_snapshot.get("bars")
                if isinstance(bars, list) and len(bars) >= 5:
                    feats = compute_features(bars)
                    result["features"] = feats
                    result["feature_engine"] = "ready" if feats.get("ready") else "insufficient_bars"
                    if feats.get("ready") and result.get("acquisition_state") == "CAPTURE_COMPLETE":
                        # Research bias only — does not authorize production
                        bias = feats.get("bias")
                        if bias and result.get("confidence_available") is not True:
                            result["details"] = (
                                (result.get("details") or "")
                                + f" Features ready (bars={feats.get('bar_count')}, bias={bias})."
                            ).strip()
                else:
                    result["feature_engine"] = "no_history"
            except Exception as fe:
                result["feature_engine"] = f"error:{type(fe).__name__}"
            if ohlc_missing_reason:
                result.setdefault("observation", {})
                if isinstance(result.get("observation"), dict):
                    result["observation"]["ohlc_missing_reason"] = ohlc_missing_reason
                    result["observation"]["worker_connected"] = worker_connected

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
    # Additive subscriber inbox (does not affect analysis / executor publish)
    try:
        notif = getattr(request.app.state, "notifications", None)
        if notif is not None:
            await notif.emit_signal(
                account_id,
                str(result.get("signal") or ""),
                float(result.get("confidence") or 0),
                str(result.get("rule_name") or ""),
                str(result.get("details") or ""),
                pair=(symbol or None),
            )
    except Exception:
        pass
    # Publish BUY/SELL for MT5 AEGIS_Executor.mq5 (HTTP poll)
    try:
        exec_svc = getattr(request.app.state, "executor_signals", None)
        side = str(result.get("signal") or "").upper()
        sym = (symbol or "").strip() if symbol else ""
        if exec_svc is not None and side in ("BUY", "SELL") and sym:
            vol = None
            try:
                lot = result.get("execution", {}) if isinstance(result.get("execution"), dict) else {}
                vol = lot.get("volume") or lot.get("lots") or result.get("calculated_lot_size")
            except Exception:
                vol = None
            # Only publish to MT5 Executor for Good/tradeable instruments
            reg = getattr(request.app.state, "registry_service", None) or getattr(request.app.state, "registry", None)
            allow_pub = True
            pub_reason = "ok"
            if reg is not None:
                try:
                    rows = reg.list_instruments(tradeable_only=False)
                    m = next((r for r in rows if str(r.get("instrument") or "").upper() == sym.upper().split(".")[0]), None)
                    if m is None:
                        allow_pub, pub_reason = False, "unknown_instrument"
                    elif not m.get("good") or not m.get("tradeable"):
                        allow_pub, pub_reason = False, f"not_good:{m.get('router_status')}"
                except Exception as _re:
                    pub_reason = f"registry_check_error:{_re}"
            if allow_pub:
                # Portfolio risk: equity × tolerance → lot + max pairs (MultiSymbol)
                sized_vol = float(vol) if vol is not None else None
                risk_meta = None
                try:
                    pr = getattr(request.app.state, "portfolio_risk", None)
                    sub_svc = getattr(request.app.state, "subscription_service", None)
                    plan_code = "demo"
                    if sub_svc is not None:
                        try:
                            rec = await sub_svc.get_status(account_id)
                            if isinstance(rec, dict):
                                plan_code = rec.get("plan") or "demo"
                        except Exception:
                            pass
                    if pr is not None:
                        risk_meta = await pr.size_order(account_id, sym, plan_code)
                        result["portfolio_risk"] = risk_meta
                        if not risk_meta.get("allow"):
                            allow_pub = False
                            pub_reason = risk_meta.get("reason") or "risk_blocked"
                        else:
                            sized_vol = float(risk_meta.get("volume") or sized_vol or 0.01)
                except Exception as _re:
                    result["portfolio_risk_error"] = str(_re)
                if allow_pub:
                    exec_svc.publish(
                        account_id=account_id,
                        symbol=sym,
                        side=side,
                        confidence=float(result.get("confidence") or 0),
                        rule_name=str(result.get("rule_name") or ""),
                        volume=sized_vol,
                        stop_loss=result.get("stop_loss") or result.get("sl"),
                        take_profit=result.get("take_profit") or result.get("tp"),
                        details=str(result.get("details") or "")[:500],
                    )
                    result["executor_published"] = True
                    result["executor_publish_reason"] = pub_reason
                    result["executor_volume"] = sized_vol
                else:
                    result["executor_published"] = False
                    result["executor_publish_reason"] = pub_reason
            else:
                result["executor_published"] = False
                result["executor_publish_reason"] = pub_reason
    except Exception as _ex:
        result["executor_published"] = False

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
                auto.portfolio_risk = getattr(request.app.state, "portfolio_risk", None)
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
