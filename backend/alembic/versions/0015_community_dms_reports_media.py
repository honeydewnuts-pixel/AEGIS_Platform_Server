"""DMs, reports, message attachments for community.

Revision ID: 0015_community_full
Revises: 0014_community_profiles
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_community_full"
down_revision = "0014_community_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("attachment_url", sa.String(512), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_mime", sa.String(64), nullable=True))

    op.create_table(
        "dm_threads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_a", sa.String(64), nullable=False, index=True),
        sa.Column("account_b", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dm_threads_pair", "dm_threads", ["account_a", "account_b"], unique=True)

    op.create_table(
        "dm_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("thread_id", sa.String(64), nullable=False, index=True),
        sa.Column("sender_id", sa.String(64), nullable=False, index=True),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(512), nullable=True),
        sa.Column("attachment_mime", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "chat_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reporter_id", sa.String(64), nullable=False, index=True),
        sa.Column("target_type", sa.String(16), nullable=False),  # room | dm
        sa.Column("target_message_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.String(64), nullable=True),
        sa.Column("thread_id", sa.String(64), nullable=True),
        sa.Column("reason", sa.String(512), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolver_note", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("chat_reports")
    op.drop_table("dm_messages")
    op.drop_index("ix_dm_threads_pair", table_name="dm_threads")
    op.drop_table("dm_threads")
    op.drop_column("chat_messages", "attachment_mime")
    op.drop_column("chat_messages", "attachment_url")
