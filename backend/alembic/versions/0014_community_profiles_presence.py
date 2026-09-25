"""Community profiles (display name) + presence.

Revision ID: 0014_community_profiles
Revises: 0013_community_ai
"""
from alembic import op
import sqlalchemy as sa

revision = "0014_community_profiles"
down_revision = "0013_community_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_profiles",
        sa.Column("account_id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(32), nullable=False),
        sa.Column("display_name_lower", sa.String(32), nullable=False, unique=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_community_profiles_last_seen", "community_profiles", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_community_profiles_last_seen", table_name="community_profiles")
    op.drop_table("community_profiles")
