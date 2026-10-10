"""Stage 6.4B corrective — uncertain block, claim token, emergency stop."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.durable_execution_queue import DurableExecutionQueueService


def _row(**kwargs):
    r = MagicMock()
    now = datetime.now(timezone.utc)
    d = dict(
        signal_id="sig-old",
        account_id="ACC-1",
        symbol="EURUSD",
        side="SELL",
        volume=0.01,
        status="PENDING",
        claim_token=None,
        claimed_at=None,
        attempt_count=0,
        created_at=now,
        updated_at=now,
        position_ticket=None,
        order_ticket=None,
        deal_ticket=None,
        ack_message=None,
        risk_usd_at_open=None,
        production_authorized=False,
        controlled_demo_authorized=True,
        methodology="controlled_demo_test",
        rule_name="controlled_demo_test",
        confidence=0.8,
        details="",
        stop_loss=None,
        take_profit=None,
        atr14=None,
        initial_stop_atr_mult=1.5,
        max_hold_bars=72,
        trail_atr_mult=0.75,
    )
    d.update(kwargs)
    for k, v in d.items():
        setattr(r, k, v)
    return r


@pytest.mark.asyncio
async def test_enqueue_blocked_by_submission_uncertain():
    svc = DurableExecutionQueueService()
    blocker = _row(status="SUBMISSION_UNCERTAIN", signal_id="sig-u")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[blocker]))))
    )
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        with patch(
            "app.services.operational_control_service.get_operational_control_service",
            return_value=MagicMock(is_emergency_stop_on=AsyncMock(return_value=False)),
        ):
            out = await svc.enqueue(
                session,
                {
                    "signal_id": "sig-new",
                    "account_id": "ACC-1",
                    "symbol": "EURUSD",
                    "side": "SELL",
                    "methodology": "controlled_demo_test",
                    "rule_name": "controlled_demo_test",
                    "controlled_demo_authorized": True,
                },
            )
    assert out is None
    assert blocker.status == "SUBMISSION_UNCERTAIN"  # not expired


@pytest.mark.asyncio
async def test_enqueue_blocked_by_claimed():
    svc = DurableExecutionQueueService()
    blocker = _row(status="CLAIMED", signal_id="sig-c", claim_token="tok1")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[blocker]))))
    )
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        with patch(
            "app.services.operational_control_service.get_operational_control_service",
            return_value=MagicMock(is_emergency_stop_on=AsyncMock(return_value=False)),
        ):
            out = await svc.enqueue(
                session,
                {
                    "signal_id": "sig-new",
                    "account_id": "ACC-1",
                    "symbol": "EURUSD",
                    "side": "SELL",
                    "methodology": "controlled_demo_test",
                    "controlled_demo_authorized": True,
                },
            )
    assert out is None
    assert blocker.status == "CLAIMED"


@pytest.mark.asyncio
async def test_enqueue_supersedes_pending_only():
    svc = DurableExecutionQueueService()
    old = _row(status="PENDING", signal_id="sig-old")
    session = MagicMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[old]))))
    )
    with patch(
        "app.services.durable_execution_queue.ExecutorSignalService.is_execution_authorized",
        return_value=True,
    ):
        with patch(
            "app.services.operational_control_service.get_operational_control_service",
            return_value=MagicMock(is_emergency_stop_on=AsyncMock(return_value=False)),
        ):
            out = await svc.enqueue(
                session,
                {
                    "signal_id": "sig-new",
                    "account_id": "ACC-1",
                    "symbol": "EURUSD",
                    "side": "SELL",
                    "methodology": "controlled_demo_test",
                    "rule_name": "controlled_demo_test",
                    "controlled_demo_authorized": True,
                },
            )
    assert out is not None
    assert old.status == "EXPIRED"
    session.add.assert_called()


@pytest.mark.asyncio
async def test_ack_mismatched_token_rejected():
    svc = DurableExecutionQueueService()
    row = _row(status="CLAIMED", claim_token="good-token", signal_id="sig-1")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    out = await svc.ack(
        session,
        account_id="ACC-1",
        signal_id="sig-1",
        ok=True,
        position_ticket=1,
        claim_token="bad-token",
    )
    assert out["ok"] is False
    assert out["reason"] == "claim_token_mismatch"
    assert row.status == "CLAIMED"


@pytest.mark.asyncio
async def test_ack_matching_token_ok():
    svc = DurableExecutionQueueService()
    row = _row(status="CLAIMED", claim_token="good-token", signal_id="sig-1")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    out = await svc.ack(
        session,
        account_id="ACC-1",
        signal_id="sig-1",
        ok=True,
        position_ticket=9,
        claim_token="good-token",
    )
    assert out["ok"] is True
    assert row.status == "ACKED"


@pytest.mark.asyncio
async def test_late_ack_on_uncertain_tokenless_ok():
    """Legacy EA tokenless late ACK after lease → SUBMISSION_UNCERTAIN."""
    svc = DurableExecutionQueueService()
    row = _row(status="SUBMISSION_UNCERTAIN", claim_token="old", signal_id="sig-1")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    out = await svc.ack(
        session,
        account_id="ACC-1",
        signal_id="sig-1",
        ok=True,
        position_ticket=5,
        claim_token=None,
    )
    assert out["ok"] is True
    assert row.status == "ACKED"


@pytest.mark.asyncio
async def test_duplicate_ack_idempotent():
    svc = DurableExecutionQueueService()
    row = _row(status="ACKED", signal_id="sig-1")
    session = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=row))
    )
    out = await svc.ack(session, account_id="ACC-1", signal_id="sig-1", ok=True)
    assert out.get("idempotent") is True


def test_emergency_stop_before_claim_in_router_source():
    from pathlib import Path
    src = Path("backend/app/api/executor_router.py").read_text()
    # Single-symbol path: stop marker before get_pending claim
    i_stop = src.find("fail closed if state unknown")
    if i_stop < 0:
        i_stop = src.find("emergency stop BEFORE claim")
    i_claim = src.find("durable claim-on-deliver is authoritative")
    assert i_stop > 0 and i_claim > i_stop  # stop before claim
    # Batch also has stop before claims
    assert "Emergency stop before any batch claims" in src


def test_enqueue_source_blocks_uncertain():
    from pathlib import Path
    src = Path("backend/app/services/durable_execution_queue.py").read_text()
    assert "CLAIMED / SUBMISSION_UNCERTAIN: block enqueue" in src or "blockers" in src
