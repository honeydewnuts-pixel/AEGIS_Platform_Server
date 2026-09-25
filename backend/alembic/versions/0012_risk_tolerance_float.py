"""Allow fractional risk tolerance pct (0.5, 2.5, … 50).

Revision ID: 0012_risk_tolerance_float
Revises: 0011_portfolio_risk
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_risk_tolerance_float"
down_revision = "0011_portfolio_risk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "risk_tolerance_pct",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        existing_server_default="25",
        postgresql_using="risk_tolerance_pct::double precision",
    )


def downgrade() -> None:
    op.alter_column(
        "subscriptions",
        "risk_tolerance_pct",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="ROUND(risk_tolerance_pct)::integer",
    )
