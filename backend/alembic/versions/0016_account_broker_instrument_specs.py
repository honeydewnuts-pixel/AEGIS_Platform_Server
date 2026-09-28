"""Account type + broker instrument specifications for standard/micro/custom.

Revision ID: 0016_broker_acct_specs
Revises: 0015_community_full

NOTE: Revision id must be <= 32 chars (Postgres alembic_version.version_num).
Idempotent: safe if columns/table partially applied after a failed stamp.
"""
from alembic import op

revision = "0016_broker_acct_specs"
down_revision = "0015_community_full"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: prior deploy may have applied DDL before version stamp failed
    # (version string was too long for varchar(32)).
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS account_type VARCHAR(32) NOT NULL DEFAULT 'standard';
        """
    )
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS account_currency VARCHAR(16) NOT NULL DEFAULT 'USD';
        """
    )
    op.execute(
        """
        ALTER TABLE subscriptions
          ADD COLUMN IF NOT EXISTS broker_id VARCHAR(64) NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_instrument_specs (
          symbol VARCHAR(32) NOT NULL,
          account_type VARCHAR(32) NOT NULL DEFAULT 'standard',
          broker_id VARCHAR(64) NOT NULL DEFAULT 'default',
          contract_size DOUBLE PRECISION NOT NULL,
          volume_min DOUBLE PRECISION NOT NULL,
          volume_max DOUBLE PRECISION NOT NULL,
          volume_step DOUBLE PRECISION NOT NULL,
          tick_size DOUBLE PRECISION NOT NULL,
          tick_value DOUBLE PRECISION NULL,
          margin_per_lot DOUBLE PRECISION NULL,
          base_currency VARCHAR(16) NOT NULL DEFAULT 'USD',
          quote_currency VARCHAR(16) NOT NULL DEFAULT 'USD',
          profit_currency VARCHAR(16) NOT NULL DEFAULT 'USD',
          min_notional_usd DOUBLE PRECISION NULL,
          source VARCHAR(32) NOT NULL DEFAULT 'manual',
          updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY (symbol, account_type, broker_id)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS broker_instrument_specs;")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS broker_id;")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS account_currency;")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS account_type;")
