"""lifecycle open_risk_applied tri-state (Stage 6.4A corrective)

Revision ID: 0023_lifecycle_open_risk_applied
Revises: 0022_aegis_executor_presence

Semantics:
  NULL  = historical/unknown — do NOT auto-recover (avoid double-count)
  false = explicitly not applied to portfolio — eligible for recovery
  true  = portfolio open_risk_usd was incremented for this row
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_lifecycle_open_risk_applied"
down_revision: Union[str, None] = "0022_aegis_executor_presence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aegis_position_lifecycle",
        sa.Column(
            "open_risk_applied",
            sa.Boolean(),
            nullable=True,
            server_default=None,
        ),
    )
    # Existing rows remain NULL (ambiguous). New rows set false/true in app code.


def downgrade() -> None:
    op.drop_column("aegis_position_lifecycle", "open_risk_applied")
