"""add source aggregate version to monthly reports

Revision ID: d6e8f1a3b5c7
Revises: c5d8e1f3a7b2
Create Date: 2026-11-05 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d6e8f1a3b5c7"
down_revision: Union[str, Sequence[str], None] = "c5d8e1f3a7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "monthly_reports",
        sa.Column(
            "source_aggregate_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("monthly_reports", "source_aggregate_version")
