import uuid

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Category, Expense


def get_budget(db: Session, budget_id: uuid.UUID) -> Budget | None:
    return db.get(Budget, budget_id)


def get_budgets_for_user(db: Session, user_id: uuid.UUID) -> list[Budget]:
    return list(db.scalars(select(Budget).where(Budget.user_id == user_id).order_by(Budget.period_start.desc())).all())


def create_budget(db: Session, **values) -> Budget:
    item = Budget(**values)
    db.add(item)
    return item


def get_category(db: Session, budget_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
    return db.scalar(select(Category).where(Category.budget_id == budget_id, Category.category_id == category_id))


def get_categories(db: Session, budget_id: uuid.UUID) -> list[Category]:
    return list(db.scalars(select(Category).where(Category.budget_id == budget_id).order_by(Category.name)).all())


def create_category(db: Session, budget_id: uuid.UUID, **values) -> Category:
    item = Category(budget_id=budget_id, **values)
    db.add(item)
    return item


def get_expense(db: Session, budget_id: uuid.UUID, expense_id: uuid.UUID) -> Expense | None:
    return db.scalar(select(Expense).where(Expense.budget_id == budget_id, Expense.expense_id == expense_id))


def get_expenses(db: Session, budget_id: uuid.UUID) -> list[Expense]:
    return list(db.scalars(select(Expense).where(Expense.budget_id == budget_id).order_by(Expense.occurred_at.desc())).all())


def create_expense(db: Session, budget_id: uuid.UUID, **values) -> Expense:
    item = Expense(budget_id=budget_id, **values)
    db.add(item)
    return item


def expense_total(db: Session, budget_id: uuid.UUID) -> Decimal:
    return db.scalar(select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(Expense.budget_id == budget_id))


def category_limits_total(db: Session, budget_id: uuid.UUID, exclude_category_id: uuid.UUID | None = None) -> Decimal:
    statement = select(func.coalesce(func.sum(Category.limit_amount), Decimal("0.00"))).where(Category.budget_id == budget_id)
    if exclude_category_id is not None:
        statement = statement.where(Category.category_id != exclude_category_id)
    return db.scalar(statement)


def category_expense_total(
    db: Session,
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
) -> Decimal:
    statement = select(func.coalesce(func.sum(Expense.amount), Decimal("0.00"))).where(
        Expense.budget_id == budget_id,
        Expense.category_id == category_id,
    )
    return db.scalar(statement)