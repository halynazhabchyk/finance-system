"""add report category totals and processed event tracking

Revision ID: 7b2c4f8e1a63
Revises: 3e95d0f17c7a
Create Date: 2026-10-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b2c4f8e1a63"
down_revision: Union[str, Sequence[str], None] = "3e95d0f17c7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_table(
        "report_category_totals",
        sa.Column("category_total_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("category_name", sa.String(length=100), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_expenses", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("category_total_id"),
        sa.UniqueConstraint("report_id", "category_name", name="uq_report_category_name"),
    )
    op.create_index(op.f("ix_report_category_totals_report_id"), "report_category_totals", ["report_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_report_category_totals_report_id"), table_name="report_category_totals")
    op.drop_table("report_category_totals")
    op.drop_table("processed_events")
