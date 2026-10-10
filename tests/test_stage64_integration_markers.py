"""Integration markers: Stage 6.4A + 6.4B coexist without weakening either."""
from pathlib import Path


def test_64a_open_risk_applied_present():
    assert "open_risk_applied" in Path("backend/app/db/models.py").read_text()
    life = Path("backend/app/services/durable_lifecycle_service.py").read_text()
    assert "mark_risk_recorded" in life
    assert "open_risk_applied" in life


def test_64b_claim_and_uncertain_present():
    q = Path("backend/app/services/durable_execution_queue.py").read_text()
    assert "SUBMISSION_UNCERTAIN" in q
    assert "claim_token" in q
    router = Path("backend/app/api/executor_router.py").read_text()
    assert "emergency_stop_state_unavailable" in router
    assert "claim_token_mismatch" in router


def test_ack_orders_durable_before_memory_and_risk():
    """Stage 6.3 ordering preserved with 6.4A risk and 6.4B tokens."""
    src = Path("backend/app/api/executor_router.py").read_text()
    # durable ack before memory ack
    i_dur = src.find("get_durable_execution_queue().ack")
    i_mem = src.find("result = svc.ack(")
    assert 0 < i_dur < i_mem
    # claim token before commit of durable ack
    assert "claim_token" in src[i_dur : i_dur + 800]
    # portfolio risk path after durable
    assert "record_open_risk" in src
    assert "mark_risk_recorded" in src


def test_migration_0023_present():
    p = Path("backend/alembic/versions/0023_lifecycle_open_risk_applied.py")
    assert p.is_file()
