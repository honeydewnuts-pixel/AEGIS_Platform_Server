"""Add risk_preset to subscriptions.

Revision ID: 0008_risk_preset
Revises: 0007_commercial_plans
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_risk_preset"
down_revision = "0007_commercial_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("risk_preset", sa.String(length=20), nullable=False, server_default="standard"),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "risk_preset")
