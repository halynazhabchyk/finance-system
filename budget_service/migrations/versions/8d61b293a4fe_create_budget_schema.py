"""create budget schema

Revision ID: 8d61b293a4fe
Revises:
Create Date: 2026-10-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d61b293a4fe"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("budget_id"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_budgets_user_period"),
    )
    op.create_index(op.f("ix_budgets_user_id"), "budgets", ["user_id"], unique=False)
    op.create_table(
        "categories",
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.budget_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id"),
        sa.UniqueConstraint("budget_id", "name", name="uq_categories_budget_name"),
    )
    op.create_index(op.f("ix_categories_budget_id"), "categories", ["budget_id"], unique=False)
    op.create_table(
        "expenses",
        sa.Column("expense_id", sa.UUID(), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.budget_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.category_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("expense_id"),
    )
    op.create_index(op.f("ix_expenses_budget_id"), "expenses", ["budget_id"], unique=False)
    op.create_index(op.f("ix_expenses_category_id"), "expenses", ["category_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_expenses_category_id"), table_name="expenses")
    op.drop_index(op.f("ix_expenses_budget_id"), table_name="expenses")
    op.drop_table("expenses")
    op.drop_index(op.f("ix_categories_budget_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_index(op.f("ix_budgets_user_id"), table_name="budgets")
    op.drop_table("budgets")
