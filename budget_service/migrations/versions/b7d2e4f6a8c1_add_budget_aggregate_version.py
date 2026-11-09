"""add aggregate version to budgets

Revision ID: b7d2e4f6a8c1
Revises: e7f4a8b2c1d0
Create Date: 2026-11-05 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7d2e4f6a8c1"
down_revision: Union[str, Sequence[str], None] = "e7f4a8b2c1d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "aggregate_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("budgets", "aggregate_version")
