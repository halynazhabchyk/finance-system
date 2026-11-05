"""align budget schema with ORM constraints

Revision ID: c4e7a9b2d1f0
Revises: 8d61b293a4fe
Create Date: 2026-10-31 16:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e7a9b2d1f0"
down_revision: Union[str, Sequence[str], None] = "8d61b293a4fe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_categories_budget_category_id",
        "categories",
        ["budget_id", "category_id"],
    )
    op.drop_constraint(
        "expenses_category_id_fkey",
        "expenses",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_expenses_budget_category",
        "expenses",
        "categories",
        ["budget_id", "category_id"],
        ["budget_id", "category_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_budgets_total_amount_positive",
        "budgets",
        "total_amount > 0",
    )
    op.create_check_constraint(
        "ck_budgets_valid_period",
        "budgets",
        "period_start <= period_end",
    )
    op.create_check_constraint(
        "ck_categories_limit_positive",
        "categories",
        "limit_amount > 0",
    )
    op.create_check_constraint(
        "ck_categories_name_not_empty",
        "categories",
        "length(trim(name)) > 0",
    )
    op.create_check_constraint(
        "ck_expenses_amount_positive",
        "expenses",
        "amount > 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_expenses_amount_positive", "expenses", type_="check")
    op.drop_constraint("ck_categories_name_not_empty", "categories", type_="check")
    op.drop_constraint("ck_categories_limit_positive", "categories", type_="check")
    op.drop_constraint("ck_budgets_valid_period", "budgets", type_="check")
    op.drop_constraint("ck_budgets_total_amount_positive", "budgets", type_="check")
    op.drop_constraint("fk_expenses_budget_category", "expenses", type_="foreignkey")
    op.create_foreign_key(
        "expenses_category_id_fkey",
        "expenses",
        "categories",
        ["category_id"],
        ["category_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "uq_categories_budget_category_id",
        "categories",
        type_="unique",
    )
