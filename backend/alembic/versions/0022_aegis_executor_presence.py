"""aegis_executor_presence durable last_seen (Stage 6.2I)

Revision ID: 0022_aegis_executor_presence
Revises: 0021_aegis_operational_control
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_aegis_executor_presence"
down_revision: Union[str, None] = "0021_aegis_operational_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aegis_executor_presence",
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("client_type", sa.String(length=64), nullable=False, server_default="AEGIS_Executor"),
        sa.Column("executor_version", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("execution_mode", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("last_symbol", sa.String(length=64), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_id"),
    )


def downgrade() -> None:
    op.drop_table("aegis_executor_presence")
