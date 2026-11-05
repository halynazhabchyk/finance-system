"""create monthly reports read model

Revision ID: 3e95d0f17c7a
Revises:
Create Date: 2026-10-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3e95d0f17c7a"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monthly_reports",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("total_budget", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_expenses", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_monthly_reports_user_period"),
    )
    op.create_index(op.f("ix_monthly_reports_user_id"), "monthly_reports", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_monthly_reports_user_id"), table_name="monthly_reports")
    op.drop_table("monthly_reports")
