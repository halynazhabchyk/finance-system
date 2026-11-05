"""add currency to budgets

Revision ID: e7f4a8b2c1d0
Revises: c4e7a9b2d1f0
Create Date: 2026-11-01 15:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f4a8b2c1d0"
down_revision: Union[str, Sequence[str], None] = "c4e7a9b2d1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "budgets",
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="UAH",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("budgets", "currency")
