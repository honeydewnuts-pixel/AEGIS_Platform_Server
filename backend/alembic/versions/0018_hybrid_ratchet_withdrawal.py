"""Hybrid Ratchet 70/30 withdrawal tables.

Revision ID: 0018
Revises: 0017
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "withdrawal_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("start_equity", sa.Float(), nullable=False),
        sa.Column("risk_per_trade_pct", sa.Float(), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("cap", sa.Float(), nullable=False),
        sa.Column("armed", sa.Boolean(), nullable=False),
        sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("cumulative_withdrawn", sa.Float(), nullable=False),
        sa.Column("eligible_balance", sa.Float(), nullable=False),
        sa.Column("retained_profit_total", sa.Float(), nullable=False),
        sa.Column("realized_trading_pnl", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_withdrawal_accounts_account_id", "withdrawal_accounts", ["account_id"])
    op.create_index("ix_withdrawal_accounts_symbol", "withdrawal_accounts", ["symbol"])

    op.create_table(
        "withdrawal_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("trade_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("excess", sa.Float(), nullable=False),
        sa.Column("to_eligible", sa.Float(), nullable=False),
        sa.Column("to_cap", sa.Float(), nullable=False),
        sa.Column("equity_after", sa.Float(), nullable=False),
        sa.Column("cap_after", sa.Float(), nullable=False),
        sa.Column("detail", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "trade_id", "event_type", name="uq_withdrawal_ledger_idem"),
    )
    op.create_index("ix_withdrawal_ledger_account_id", "withdrawal_ledger", ["account_id"])
    op.create_index("ix_withdrawal_ledger_created_at", "withdrawal_ledger", ["created_at"])

    op.create_table(
        "withdrawal_requests",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("detail", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_withdrawal_requests_account_id", "withdrawal_requests", ["account_id"])


def downgrade() -> None:
    op.drop_table("withdrawal_requests")
    op.drop_table("withdrawal_ledger")
    op.drop_table("withdrawal_accounts")
