"""Business logic for budgets."""

import uuid
import os
import socket
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import budgets as repository
from app.schemas import BudgetCreate, BudgetUpdate
from app.services.common import (
    budget_or_404,
    commit,
    validate_period,
)
from app.integrations.events import (
    build_budget_deleted_event,
    publish_budget_deleted,
    publish_budget_snapshot,
)


def list_budgets(db: Session, user_id: uuid.UUID):
    return repository.get_budgets_for_user(db, user_id)


def get_budget_summary(db: Session, budget_id: uuid.UUID, user_id: uuid.UUID):
    budget = budget_or_404(db, budget_id, user_id)
    expenses = repository.get_expenses(db, budget_id)
    used_amount = sum((expense.amount for expense in expenses), Decimal("0.00"))
    categories = []
    for category in repository.get_categories(db, budget_id):
        category_used = repository.category_expense_total(
            db,
            budget_id,
            category.category_id,
        )
        categories.append(
            {
                "category_id": category.category_id,
                "budget_id": category.budget_id,
                "name": category.name,
                "limit_amount": category.limit_amount,
                "currency": budget.currency,
                "used_amount": category_used,
                "available_amount": category.limit_amount - category_used,
                "limit_exceeded": category_used > category.limit_amount,
            }
        )
    return {
        "budget": budget,
        "used_amount": used_amount,
        "available_amount": budget.total_amount - used_amount,
        "categories": categories,
        "expenses": expenses,
        "service": "budget-service",
        "instance_id": os.getenv("HOSTNAME") or socket.gethostname(),
    }


def create_budget(
    db: Session,
    user_id: uuid.UUID,
    payload: BudgetCreate,
):
    validate_period(payload.period_start, payload.period_end)
    try:
        budget = repository.create_budget(
            db,
            user_id=user_id,
            **payload.model_dump(),
        )
        commit(db)
        db.refresh(budget)
        publish_budget_snapshot(db, budget, "BudgetCreated")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
    return budget


def update_budget(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: BudgetUpdate,
):
    try:
        budget = budget_or_404(db, budget_id, user_id)
        values = payload.model_dump(exclude_unset=True)
        period_start = values.get("period_start", budget.period_start)
        period_end = values.get("period_end", budget.period_end)
        total_amount = values.get("total_amount", budget.total_amount)
        validate_period(period_start, period_end)
        if total_amount < repository.category_limits_total(db, budget_id):
            raise HTTPException(
                status_code=422,
                detail="Budget total cannot be lower than allocated category limits.",
            )
        if "period_start" in values or "period_end" in values:
            if any(
                not period_start <= expense.occurred_at <= period_end
                for expense in repository.get_expenses(db, budget_id)
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Budget period cannot exclude existing expenses.",
                )
        for name, value in values.items():
            setattr(budget, name, value)
        commit(db)
        db.refresh(budget)
        publish_budget_snapshot(db, budget, "BudgetUpdated")
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
    return budget


def delete_budget(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        budget = budget_or_404(db, budget_id, user_id)
        deleted_event = build_budget_deleted_event(budget)
        db.delete(budget)
        commit(db)
        publish_budget_deleted(deleted_event)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The budget database is temporarily unavailable.",
        ) from error
