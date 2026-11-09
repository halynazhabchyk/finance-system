"""Use cases for budget expenses.

Creating an expense is step T1 of the "create expense" SAGA: the expense
(PENDING), the saga state and the ExpenseCreated outbox row are committed
in one local transaction.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from shared.errors import BusinessRuleError, ConflictError, NotFoundError
from app.db.transaction import write_transaction
from app.integrations.events import expense_payload, saga_fields
from app.models import Budget, Expense, SagaInstance
from app.models.expense import EXPENSE_CONFIRMED, EXPENSE_PENDING
from app.repositories import budgets as repository
from app.schemas import ExpenseCreate, ExpenseUpdate
from app.services.common import budget_or_404, record_budget_change
from app.services.saga import saga_service


def list_expenses(db: Session, budget_id: uuid.UUID, user_id: uuid.UUID) -> list[Expense]:
    budget_or_404(db, budget_id, user_id)
    # Cancelled expenses stay visible in the list as operation history.
    return repository.get_expenses(db, budget_id, include_cancelled=True)


def get_expense_saga(
    db: Session,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
) -> SagaInstance:
    budget_or_404(db, budget_id, user_id)
    _expense_or_404(db, budget_id, expense_id)
    saga = saga_service.get_for_expense(db, expense_id)
    if saga is None:
        raise NotFoundError("No saga is recorded for this expense.")
    return saga


def create_expense(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ExpenseCreate,
) -> Expense:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        _ensure_category_and_date(db, budget, payload.category_id, payload.occurred_at)
        expense = repository.create_expense(
            db,
            budget_id,
            saga_status=EXPENSE_PENDING,
            **payload.model_dump(),
        )
        db.flush()
        saga = saga_service.start_create_expense(db, expense.expense_id)
        record_budget_change(
            db,
            budget,
            "ExpenseCreated",
            aggregate_type="Expense",
            aggregate_id=expense.expense_id,
            extra=saga_fields(saga, expense),
        )
    db.refresh(expense)
    return expense


def update_expense(
    db: Session,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ExpenseUpdate,
) -> Expense:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        expense = _changeable_expense(db, budget_id, expense_id)
        values = payload.model_dump(exclude_unset=True)
        _ensure_category_and_date(
            db,
            budget,
            values.get("category_id", expense.category_id),
            values.get("occurred_at", expense.occurred_at),
        )
        for name, value in values.items():
            setattr(expense, name, value)
        record_budget_change(
            db,
            budget,
            "ExpenseUpdated",
            aggregate_type="Expense",
            aggregate_id=expense.expense_id,
        )
    db.refresh(expense)
    return expense


def delete_expense(
    db: Session,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    with write_transaction(db):
        budget = budget_or_404(db, budget_id, user_id, for_update=True)
        expense = _changeable_expense(db, budget_id, expense_id)
        deleted_expense = expense_payload(expense)
        db.delete(expense)
        record_budget_change(
            db,
            budget,
            "ExpenseDeleted",
            aggregate_type="Expense",
            aggregate_id=expense.expense_id,
            deleted_expense=deleted_expense,
        )


def ensure_expense_confirmed(expense: Expense) -> None:
    """A saga in flight or a compensated expense must not be changed by users."""
    if expense.saga_status != EXPENSE_CONFIRMED:
        raise ConflictError(f"Expense in state {expense.saga_status} cannot be changed.")


def _expense_or_404(db: Session, budget_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    expense = repository.get_expense(db, budget_id, expense_id)
    if expense is None:
        raise NotFoundError("Expense was not found.")
    return expense


def _changeable_expense(db: Session, budget_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    expense = _expense_or_404(db, budget_id, expense_id)
    ensure_expense_confirmed(expense)
    return expense


def _ensure_category_and_date(
    db: Session,
    budget: Budget,
    category_id: uuid.UUID,
    occurred_at: date,
) -> None:
    """The category belongs to the budget and the date lies inside its period."""
    if repository.get_category(db, budget.budget_id, category_id) is None:
        raise NotFoundError("Category was not found in this budget.")
    if not budget.period_start <= occurred_at <= budget.period_end:
        raise BusinessRuleError("Expense date must be inside the budget period.")
