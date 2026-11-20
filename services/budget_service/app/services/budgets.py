"""Use cases for budgets."""

from __future__ import annotations

import os
import socket
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from shared.errors import BusinessRuleError
from app.db.transaction import write_transaction
from app.integrations.events import build_budget_deleted_event
from app.integrations.outbox import add_outbox_event
from app.models import Budget
from app.repositories import budgets as repository
from app.schemas import BudgetCreate, BudgetUpdate
from app.services.common import budget_or_404, record_budget_change, validate_period

SERVICE_NAME = "budget-service"


def list_budgets(
    db: Session,
    user_id: uuid.UUID,
    *,
    period: str | None = None,
) -> list[Budget]:
    """Budgets of the user, optionally only the one covering ``period`` (YYYY-MM)."""
    period_start = parse_budget_period(period) if period is not None else None
    return repository.get_budgets_for_user(db, user_id, period_start=period_start)


def parse_budget_period(period: str) -> date:
    """Convert ``YYYY-MM`` into the first day of that month (a budget's period_start)."""
    try:
        year_text, month_text = period.split("-")
        return date(int(year_text), int(month_text), 1)
    except ValueError as error:
        raise BusinessRuleError("Period must have the format YYYY-MM.") from error


def get_budget_summary(db: Session, budget_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    budget = budget_or_404(db, budget_id, user_id)
    expenses = repository.get_expenses(db, budget_id)
    used_amount = sum((expense.amount for expense in expenses), Decimal("0.00"))
    return {
        "budget": budget,
        "used_amount": used_amount,
        "available_amount": budget.total_amount - used_amount,
        "categories": [
            _category_summary(db, budget, category)
            for category in repository.get_categories(db, budget_id)
        ],
        "expenses": expenses,
        "service": SERVICE_NAME,
        "instance_id": os.getenv("HOSTNAME") or socket.gethostname(),
    }


def create_budget(db: Session, user_id: uuid.UUID, payload: BudgetCreate) -> Budget:
    validate_period(payload.period_start, payload.period_end)
    with write_transaction(db):
        budget = repository.create_budget(db, user_id=user_id, **payload.model_dump())
        record_budget_change(db, budget, "BudgetCreated", bump_version=False)
    db.refresh(budget)
    return budget


def update_budget(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: BudgetUpdate,
) -> Budget:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        values = payload.model_dump(exclude_unset=True)
        _ensure_update_allowed(db, budget, values)
        for name, value in values.items():
            setattr(budget, name, value)
        record_budget_change(db, budget, "BudgetUpdated")
    db.refresh(budget)
    return budget


def delete_budget(db: Session, budget_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        budget.aggregate_version += 1
        deleted_event = build_budget_deleted_event(budget)
        db.delete(budget)
        add_outbox_event(db, deleted_event)


def _ensure_update_allowed(db: Session, budget: Budget, values: dict) -> None:
    """Domain invariants for a partial budget update."""
    period_start = values.get("period_start", budget.period_start)
    period_end = values.get("period_end", budget.period_end)
    total_amount = values.get("total_amount", budget.total_amount)
    validate_period(period_start, period_end)
    if total_amount < repository.category_limits_total(db, budget.budget_id):
        raise BusinessRuleError("Budget total cannot be lower than allocated category limits.")
    period_changed = "period_start" in values or "period_end" in values
    if period_changed and any(
        not period_start <= expense.occurred_at <= period_end
        for expense in repository.get_expenses(db, budget.budget_id)
    ):
        raise BusinessRuleError("Budget period cannot exclude existing expenses.")


def _category_summary(db: Session, budget: Budget, category) -> dict:
    used = repository.category_expense_total(db, budget.budget_id, category.category_id)
    return {
        "category_id": category.category_id,
        "budget_id": category.budget_id,
        "name": category.name,
        "limit_amount": category.limit_amount,
        "currency": budget.currency,
        "used_amount": used,
        "available_amount": category.limit_amount - used,
        "limit_exceeded": used > category.limit_amount,
    }
