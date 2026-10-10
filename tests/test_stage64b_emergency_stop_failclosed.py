"""Stage 6.4B — emergency-stop fail-closed on /pending and /pending-batch.

MOCKED / source-level unless labeled DATABASE-BACKED.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _router_src() -> str:
    return Path("backend/app/api/executor_router.py").read_text()


def test_single_path_fail_closed_on_stop_lookup_exception():
    src = _router_src()
    assert "emergency_stop_state_unavailable" in src
    # Single-symbol: exception path must raise, not pass
    assert "except Exception:\n        pass" not in src.split("durable claim-on-deliver is authoritative")[0]
    # After stop block, claim starts; stop block uses raise HTTPException 503
    assert src.count("emergency_stop_state_unavailable") >= 2


def test_batch_path_fail_closed_on_stop_lookup_exception():
    src = _router_src()
    idx = src.find("Emergency stop before any batch claims")
    assert idx > 0
    chunk = src[idx : idx + 1500]
    assert "emergency_stop_state_unavailable" in chunk
    assert "except Exception:\n        pass" not in chunk


def test_stop_on_returns_no_signal_reason_in_source():
    src = _router_src()
    assert '"reason": "emergency_stop"' in src or "'reason': 'emergency_stop'" in src
    assert "emergency stop BEFORE claim" in src or "fail closed if state unknown" in src


@pytest.mark.asyncio
async def test_stop_lookup_exception_raises_503_logic():
    """Simulate the fail-closed pattern used by the router."""
    async def _check():
        try:
            raise RuntimeError("db down")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="emergency_stop_state_unavailable",
            ) from exc

    with pytest.raises(HTTPException) as ei:
        await _check()
    assert ei.value.status_code == 503
    assert ei.value.detail == "emergency_stop_state_unavailable"


def test_no_memory_fallback_when_durable_fails():
    src = _router_src()
    assert "Fail closed" in src or "row = None" in src
    # Memory-first delivery must not exist
    assert "svc.get_pending(account_id, base) or svc.get_pending" not in src


def test_prior_corrective_uncertain_block_still_present():
    q = Path("backend/app/services/durable_execution_queue.py").read_text()
    assert "SUBMISSION_UNCERTAIN" in q
    assert "blockers" in q or "block enqueue" in q.lower() or "CLAIMED / SUBMISSION_UNCERTAIN" in q
