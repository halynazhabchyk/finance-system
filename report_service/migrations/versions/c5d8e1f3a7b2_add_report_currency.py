"""add currency to monthly reports

Revision ID: c5d8e1f3a7b2
Revises: 8c4e7a9b2d1f
Create Date: 2026-11-01 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d8e1f3a7b2"
down_revision: Union[str, Sequence[str], None] = "8c4e7a9b2d1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monthly_reports",
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default="UAH",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_reports", "currency")
