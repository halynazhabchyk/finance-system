"""align report schema with ORM constraints

Revision ID: 8c4e7a9b2d1f
Revises: 7b2c4f8e1a63
Create Date: 2026-10-31 16:15:00

"""
from typing import Sequence, Union

from alembic import op


revision: str = "8c4e7a9b2d1f"
down_revision: Union[str, Sequence[str], None] = "7b2c4f8e1a63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_report_category_totals_report",
        "report_category_totals",
        "monthly_reports",
        ["report_id"],
        ["report_id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        "ck_monthly_reports_budget_non_negative",
        "monthly_reports",
        "total_budget >= 0",
    )
    op.create_check_constraint(
        "ck_monthly_reports_expenses_non_negative",
        "monthly_reports",
        "total_expenses >= 0",
    )
    op.create_check_constraint(
        "ck_monthly_reports_remaining_consistent",
        "monthly_reports",
        "remaining_amount = total_budget - total_expenses",
    )
    op.create_check_constraint(
        "ck_report_category_limit_positive",
        "report_category_totals",
        "limit_amount > 0",
    )
    op.create_check_constraint(
        "ck_report_category_expenses_non_negative",
        "report_category_totals",
        "total_expenses >= 0",
    )
    op.create_check_constraint(
        "ck_report_category_name_not_empty",
        "report_category_totals",
        "length(trim(category_name)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_report_category_name_not_empty",
        "report_category_totals",
        type_="check",
    )
    op.drop_constraint(
        "ck_report_category_expenses_non_negative",
        "report_category_totals",
        type_="check",
    )
    op.drop_constraint(
        "ck_report_category_limit_positive",
        "report_category_totals",
        type_="check",
    )
    op.drop_constraint(
        "ck_monthly_reports_remaining_consistent",
        "monthly_reports",
        type_="check",
    )
    op.drop_constraint(
        "ck_monthly_reports_expenses_non_negative",
        "monthly_reports",
        type_="check",
    )
    op.drop_constraint(
        "ck_monthly_reports_budget_non_negative",
        "monthly_reports",
        type_="check",
    )
    op.drop_constraint(
        "fk_report_category_totals_report",
        "report_category_totals",
        type_="foreignkey",
    )
