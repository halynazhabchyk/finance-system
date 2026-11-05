"""Business logic for budget expenses."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import budgets as repository
from app.schemas import ExpenseCreate, ExpenseUpdate
from app.services.common import budget_or_404, commit
from app.integrations.events import publish_budget_snapshot


def list_expenses(db: Session, budget_id: uuid.UUID, user_id: uuid.UUID):
    budget = budget_or_404(db, budget_id, user_id)
    return repository.get_expenses(db, budget_id)


def create_expense(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ExpenseCreate,
):
    try:
        budget = budget_or_404(db, budget_id, user_id)
        category = repository.get_category(db, budget_id, payload.category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category was not found in this budget.")
        if not budget.period_start <= payload.occurred_at <= budget.period_end:
            raise HTTPException(status_code=422, detail="Expense date must be inside the budget period.")
        expense = repository.create_expense(db, budget_id, **payload.model_dump())
        commit(db)
        db.refresh(expense)
        publish_budget_snapshot(db, budget, "ExpenseCreated")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
    return expense


def update_expense(
    db: Session,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ExpenseUpdate,
):
    try:
        budget = budget_or_404(db, budget_id, user_id)
        expense = repository.get_expense(db, budget_id, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail="Expense was not found.")
        values = payload.model_dump(exclude_unset=True)
        category_id = values.get("category_id", expense.category_id)
        occurred_at = values.get("occurred_at", expense.occurred_at)
        if repository.get_category(db, budget_id, category_id) is None:
            raise HTTPException(status_code=404, detail="Category was not found in this budget.")
        if not budget.period_start <= occurred_at <= budget.period_end:
            raise HTTPException(status_code=422, detail="Expense date must be inside the budget period.")
        for name, value in values.items():
            setattr(expense, name, value)
        commit(db)
        db.refresh(expense)
        publish_budget_snapshot(db, budget, "ExpenseUpdated")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
    return expense


def delete_expense(
    db: Session,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        budget = budget_or_404(db, budget_id, user_id)
        expense = repository.get_expense(db, budget_id, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail="Expense was not found.")
        db.delete(expense)
        commit(db)
        publish_budget_snapshot(db, budget, "ExpenseDeleted")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
