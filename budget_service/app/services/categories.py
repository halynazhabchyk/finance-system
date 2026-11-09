"""Use cases for budget categories."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from shared.errors import BusinessRuleError, NotFoundError
from app.db.transaction import write_transaction
from app.models import Budget, Category
from app.repositories import budgets as repository
from app.schemas import CategoryCreate, CategoryUpdate
from app.services.common import budget_or_404, record_budget_change

# Category changes alter the budget snapshot, so they publish BudgetUpdated.
CATEGORY_CHANGE_EVENT = "BudgetUpdated"


def create_category(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CategoryCreate,
) -> Category:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        _ensure_limits_fit(budget, repository.category_limits_total(db, budget_id), payload.limit_amount)
        category = repository.create_category(db, budget_id, **payload.model_dump())
        record_budget_change(db, budget, CATEGORY_CHANGE_EVENT)
    db.refresh(category)
    return category


def update_category(
    db: Session,
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CategoryUpdate,
) -> Category:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        category = _category_or_404(db, budget_id, category_id)
        values = payload.model_dump(exclude_unset=True)
        other_limits = repository.category_limits_total(db, budget_id, exclude_category_id=category_id)
        _ensure_limits_fit(budget, other_limits, values.get("limit_amount", category.limit_amount))
        for name, value in values.items():
            setattr(category, name, value)
        record_budget_change(db, budget, CATEGORY_CHANGE_EVENT)
    db.refresh(category)
    return category


def delete_category(
    db: Session,
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        db.delete(_category_or_404(db, budget_id, category_id))
        record_budget_change(db, budget, CATEGORY_CHANGE_EVENT)


def _category_or_404(db: Session, budget_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    category = repository.get_category(db, budget_id, category_id)
    if category is None:
        raise NotFoundError("Category was not found.")
    return category


def _ensure_limits_fit(budget: Budget, other_limits: Decimal, new_limit: Decimal) -> None:
    """The sum of category limits must not exceed the total budget."""
    if other_limits + new_limit > budget.total_amount:
        raise BusinessRuleError("Category limits cannot exceed the total budget.")
