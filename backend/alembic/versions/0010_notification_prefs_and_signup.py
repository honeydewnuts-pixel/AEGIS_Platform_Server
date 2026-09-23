"""Notification preferences + optional signup email on subscriptions.

Revision ID: 0010_notification_prefs
Revises: 0009_notifications
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_notification_prefs"
down_revision = "0009_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_address", sa.String(), nullable=True),
        sa.Column("telegram_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("telegram_chat_id", sa.String(), nullable=True),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sms_number", sa.String(), nullable=True),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("whatsapp_number", sa.String(), nullable=True),
        sa.Column("min_confidence", sa.Float(), nullable=False, server_default="0.55"),
        sa.Column("signal_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("execution_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("system_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Track contact email for ownership / receipts (nullable for legacy rows)
    with op.batch_alter_table("subscriptions") as batch:
        batch.add_column(sa.Column("contact_email", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_column("contact_email")
    op.drop_table("notification_preferences")
