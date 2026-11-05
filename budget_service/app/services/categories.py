"""Business logic for budget categories."""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import budgets as repository
from app.schemas import CategoryCreate, CategoryUpdate
from app.services.common import budget_or_404, commit
from app.integrations.events import publish_budget_snapshot


def create_category(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CategoryCreate,
):
    try:
        budget = budget_or_404(db, budget_id, user_id)
        if repository.category_limits_total(db, budget_id) + payload.limit_amount > budget.total_amount:
            raise HTTPException(status_code=422, detail="Category limits cannot exceed the total budget.")
        category = repository.create_category(db, budget_id, **payload.model_dump())
        commit(db)
        db.refresh(category)
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
    return category


def update_category(
    db: Session,
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CategoryUpdate,
):
    try:
        budget = budget_or_404(db, budget_id, user_id)
        category = repository.get_category(db, budget_id, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category was not found.")
        values = payload.model_dump(exclude_unset=True)
        updated_limit = values.get("limit_amount", category.limit_amount)
        other_limits = repository.category_limits_total(
            db, budget_id, exclude_category_id=category_id
        )
        if other_limits + updated_limit > budget.total_amount:
            raise HTTPException(status_code=422, detail="Category limits cannot exceed the total budget.")
        for name, value in values.items():
            setattr(category, name, value)
        commit(db)
        db.refresh(category)
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
    return category


def delete_category(
    db: Session,
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        budget = budget_or_404(db, budget_id, user_id)
        category = repository.get_category(db, budget_id, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Category was not found.")
        db.delete(category)
        commit(db)
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
