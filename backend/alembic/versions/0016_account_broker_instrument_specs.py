"""Account type + broker instrument specifications for standard/micro/custom.

Revision ID: 0016_account_broker_instrument_specs
Revises: 0015_community_full
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision = "0016_account_broker_instrument_specs"
down_revision = "0015_community_full"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("account_type", sa.String(length=32), nullable=False, server_default="standard"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("account_currency", sa.String(length=16), nullable=False, server_default="USD"),
    )
    op.add_column(
        "subscriptions",
        sa.Column("broker_id", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "broker_instrument_specs",
        sa.Column("symbol", sa.String(length=32), primary_key=True),
        sa.Column("account_type", sa.String(length=32), primary_key=True, server_default="standard"),
        sa.Column("broker_id", sa.String(length=64), primary_key=True, server_default="default"),
        sa.Column("contract_size", sa.Float(), nullable=False),
        sa.Column("volume_min", sa.Float(), nullable=False),
        sa.Column("volume_max", sa.Float(), nullable=False),
        sa.Column("volume_step", sa.Float(), nullable=False),
        sa.Column("tick_size", sa.Float(), nullable=False),
        sa.Column("tick_value", sa.Float(), nullable=True),
        sa.Column("margin_per_lot", sa.Float(), nullable=True),
        sa.Column("base_currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("quote_currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("profit_currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("min_notional_usd", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("broker_instrument_specs")
    op.drop_column("subscriptions", "broker_id")
    op.drop_column("subscriptions", "account_currency")
    op.drop_column("subscriptions", "account_type")
