"""Portfolio risk: equity, tolerance %, multi-symbol mode, halt.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("account_equity_usd", sa.Float(), nullable=True))
    op.add_column("subscriptions", sa.Column("peak_equity_usd", sa.Float(), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("risk_tolerance_pct", sa.Integer(), nullable=False, server_default="25"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trading_mode", sa.String(32), nullable=False, server_default="multi_symbol"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("trading_halted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("subscriptions", sa.Column("halted_reason", sa.String(255), nullable=True))
    op.add_column(
        "subscriptions",
        sa.Column("open_risk_usd", sa.Float(), nullable=False, server_default="0"),
    )
    op.create_table(
        "instrument_min_notional",
        sa.Column("symbol", sa.String(32), primary_key=True),
        sa.Column("min_notional_usd", sa.Float(), nullable=False, server_default="50"),
        sa.Column("min_lot", sa.Float(), nullable=False, server_default="0.01"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("instrument_min_notional")
    for col in (
        "open_risk_usd",
        "halted_reason",
        "trading_halted",
        "trading_mode",
        "risk_tolerance_pct",
        "peak_equity_usd",
        "account_equity_usd",
    ):
        op.drop_column("subscriptions", col)
