"""Budget domain events published through the transactional outbox.

Only builds event dictionaries; storing them is ``app.integrations.outbox``.
"""

from __future__ import annotations

import uuid

from shared.contracts.events import new_event

from app.repositories import budgets as repository

BUDGET_SNAPSHOT_EVENT_TYPES = frozenset(
    {
        "BudgetCreated",
        "BudgetUpdated",
        "ExpenseCreated",
        "ExpenseUpdated",
        "ExpenseDeleted",
        "ExpenseCancelled",
    }
)


def expense_payload(expense) -> dict:
    """Public representation of one expense inside an event."""
    return {
        "expense_id": str(expense.expense_id),
        "category_id": str(expense.category_id),
        "amount": str(expense.amount),
        "occurred_at": expense.occurred_at.isoformat(),
        "description": expense.description,
    }


def category_payload(db, budget, category) -> dict:
    return {
        "category_id": str(category.category_id),
        "name": category.name,
        "limit_amount": str(category.limit_amount),
        "total_expenses": str(
            repository.category_expense_total(db, budget.budget_id, category.category_id)
        ),
    }


def saga_fields(saga, expense, **more) -> dict:
    """Fields that link a snapshot event to the "create expense" SAGA."""
    return {"saga_id": str(saga.saga_id), "expense_id": str(expense.expense_id), **more}


def build_budget_snapshot_event(
    db,
    budget,
    event_type: str,
    *,
    aggregate_type: str = "Budget",
    aggregate_id: uuid.UUID | None = None,
    deleted_expense: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """Full budget state after a change; consumers keep the newest aggregate_version."""
    if event_type not in BUDGET_SNAPSHOT_EVENT_TYPES:
        raise ValueError(f"Unsupported budget snapshot event type: {event_type}")
    payload = {
        "user_id": str(budget.user_id),
        "budget_id": str(budget.budget_id),
        "period_start": budget.period_start.isoformat(),
        "period_end": budget.period_end.isoformat(),
        "total_budget": str(budget.total_amount),
        "currency": budget.currency,
        "categories": [
            category_payload(db, budget, category)
            for category in repository.get_categories(db, budget.budget_id)
        ],
        "expenses": [
            expense_payload(expense) for expense in repository.get_expenses(db, budget.budget_id)
        ],
    }
    if deleted_expense is not None:
        payload["deleted_expense"] = deleted_expense
    if extra:
        payload.update(extra)
    return new_event(
        event_type,
        payload,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id or budget.budget_id),
        aggregate_version=budget.aggregate_version,
    )


def build_budget_deleted_event(budget) -> dict:
    return new_event(
        "BudgetDeleted",
        {
            "user_id": str(budget.user_id),
            "budget_id": str(budget.budget_id),
            "period_start": budget.period_start.isoformat(),
        },
        aggregate_type="Budget",
        aggregate_id=str(budget.budget_id),
        aggregate_version=budget.aggregate_version,
    )
