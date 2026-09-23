"""Add notifications inbox table (subscriber alerts).

Revision ID: 0009_notifications
Revises: 0008_risk_preset
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_notifications"
down_revision = "0008_risk_preset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="info"),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("pair", sa.String(), nullable=True),
        sa.Column("signal", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rule_name", sa.String(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("delivery_channels", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_notifications_account_id", "notifications", ["account_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_account_unread", "notifications", ["account_id", "read_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_account_unread", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_account_id", table_name="notifications")
    op.drop_table("notifications")
