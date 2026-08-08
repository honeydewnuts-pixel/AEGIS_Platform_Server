"""
Project : AEGIS
Company : Honeydewnuts Nigerian Limited

File    : brain_router.py

Exposes POST /aegis/analyze, matching the path the AEGIS Mobile app
already calls (see ApiService.kt: @POST("/aegis/analyze")).

CHANGE: now requires an `account_id` form field alongside the image.
This is new - the mobile app needs a small update (add one field to
the multipart request in ScreenCaptureService.kt) so the backend can
keep a per-account frame history. Without it, most of the rulebook's
conditions ("has crossed", "makes divergence") can't be evaluated,
since those require comparing frames over time, not just one image.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.security import verify_api_key, require_account_match, AuthContext

router = APIRouter(tags=["Brain / Vision Analysis"])


@router.post("/aegis/analyze")
async def analyze_screenshot(
    request: Request,
    image: UploadFile = File(...),
    account_id: str = Form(...),
    captured_at_ms: int | None = Form(None),
    auth: AuthContext = Depends(verify_api_key),
):
    require_account_match(auth, account_id)

    brain = request.app.state.brain_cv_service
    history_service = request.app.state.indicator_history

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted.")

    image_bytes = await image.read()

    try:
        cv_image = brain.decode_image(image_bytes)
        frame_state = brain.extract_frame_state(cv_image)
        await history_service.append_frame(account_id, frame_state, captured_at_ms)
        history = await history_service.get_history(account_id)
        result = brain.evaluate(history)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        brain.logger.exception("Screenshot analysis failed for account %s", account_id)
        raise HTTPException(status_code=500, detail="Analysis failed.") from exc

    signal_history = request.app.state.signal_history
    await signal_history.record(
        account_id, result["signal"], result["confidence"], result["rule_name"], result["details"]
    )

    result["timestamp"] = int(time.time() * 1000)  # matches AnalysisResponse.timestamp (Long, ms) in the mobile app
    return result
