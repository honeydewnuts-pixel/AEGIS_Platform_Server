"""Store broker free margin + timestamp for fail-closed sizing.

Revision ID: 0017_available_margin
Revises: 0016_broker_acct_specs
"""
from alembic import op

revision = "0017_available_margin"
down_revision = "0016_broker_acct_specs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS available_margin_usd DOUBLE PRECISION NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS margin_updated_at TIMESTAMPTZ NULL;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS margin_updated_at;")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS available_margin_usd;")
