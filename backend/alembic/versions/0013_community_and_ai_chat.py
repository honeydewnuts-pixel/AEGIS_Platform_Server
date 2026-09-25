"""Community rooms + peer messages + AEGIS AI chat history.

Revision ID: 0013_community_ai
Revises: 0012_risk_tolerance_float
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_community_ai"
down_revision = "0012_risk_tolerance_float"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.String(64), sa.ForeignKey("chat_rooms.id"), nullable=False, index=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_chat_messages_room_created", "chat_messages", ["room_id", "created_at"])

    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(64), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),  # user | assistant | system
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("ai_chat_messages")
    op.drop_index("ix_chat_messages_room_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("chat_rooms")
