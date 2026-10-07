"""aegis_execution_queue durable pending (Stage 5)

Revision ID: 0020_aegis_execution_queue
Revises: 0019_aegis_position_lifecycle
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_aegis_execution_queue"
down_revision: Union[str, None] = "0019_aegis_position_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aegis_execution_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("take_profit", sa.Float(), nullable=True),
        sa.Column("atr14", sa.Float(), nullable=True),
        sa.Column("initial_stop_atr_mult", sa.Float(), nullable=True),
        sa.Column("max_hold_bars", sa.Integer(), nullable=True),
        sa.Column("trail_atr_mult", sa.Float(), nullable=True),
        sa.Column("methodology", sa.String(length=64), nullable=False),
        sa.Column("rule_name", sa.String(length=128), nullable=False),
        sa.Column("risk_usd_at_open", sa.Float(), nullable=True),
        sa.Column("production_authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("controlled_demo_authorized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("claim_token", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("position_ticket", sa.BigInteger(), nullable=True),
        sa.Column("order_ticket", sa.BigInteger(), nullable=True),
        sa.Column("deal_ticket", sa.BigInteger(), nullable=True),
        sa.Column("ack_ok", sa.Boolean(), nullable=True),
        sa.Column("ack_message", sa.String(length=256), nullable=True),
        sa.Column("details", sa.String(length=500), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signal_id", name="uq_exec_queue_signal_id"),
    )
    op.create_index("ix_aegis_execution_queue_signal_id", "aegis_execution_queue", ["signal_id"])
    op.create_index("ix_aegis_execution_queue_account_id", "aegis_execution_queue", ["account_id"])
    op.create_index("ix_aegis_execution_queue_status", "aegis_execution_queue", ["status"])


def downgrade() -> None:
    op.drop_index("ix_aegis_execution_queue_status", table_name="aegis_execution_queue")
    op.drop_index("ix_aegis_execution_queue_account_id", table_name="aegis_execution_queue")
    op.drop_index("ix_aegis_execution_queue_signal_id", table_name="aegis_execution_queue")
    op.drop_table("aegis_execution_queue")
