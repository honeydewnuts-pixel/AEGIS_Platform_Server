"""AEGIS durable position lifecycle records.

Revision ID: 0019_aegis_position_lifecycle
Revises: 0018_hybrid_ratchet_withdrawal
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_aegis_position_lifecycle"
down_revision = "0018_hybrid_ratchet_withdrawal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aegis_position_lifecycle",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(), nullable=False, index=True),
        sa.Column("signal_id", sa.String(), nullable=False),
        sa.Column("position_ticket", sa.BigInteger(), nullable=True),
        sa.Column("order_ticket", sa.BigInteger(), nullable=True),
        sa.Column("deal_ticket", sa.BigInteger(), nullable=True),
        sa.Column("symbol", sa.String(64), nullable=False, server_default=""),
        sa.Column("side", sa.String(16), nullable=False, server_default=""),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("risk_usd_at_open", sa.Float(), nullable=True),
        sa.Column("state", sa.String(48), nullable=False, server_default="SIGNAL_QUEUED"),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("account_id", "signal_id", name="uq_lifecycle_account_signal"),
    )
    op.create_index(
        "ix_lifecycle_account_ticket",
        "aegis_position_lifecycle",
        ["account_id", "position_ticket"],
    )
    op.create_index(
        "ix_lifecycle_account_state",
        "aegis_position_lifecycle",
        ["account_id", "state"],
    )


def downgrade() -> None:
    op.drop_index("ix_lifecycle_account_state", table_name="aegis_position_lifecycle")
    op.drop_index("ix_lifecycle_account_ticket", table_name="aegis_position_lifecycle")
    op.drop_table("aegis_position_lifecycle")
