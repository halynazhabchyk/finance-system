"""Budget domain events published after committed changes."""

from __future__ import annotations

from fastapi import HTTPException, status

from shared.contracts.events import new_event
from shared.messaging.rabbitmq import RabbitMQPublishError, publish_event

from app.repositories import budgets as repository


def publish_budget_snapshot(db, budget, event_type: str) -> None:
    expenses = repository.get_expenses(db, budget.budget_id)
    categories = repository.get_categories(db, budget.budget_id)
    event = new_event(
        event_type,
        {
            "user_id": str(budget.user_id),
            "budget_id": str(budget.budget_id),
            "period_start": budget.period_start.isoformat(),
            "period_end": budget.period_end.isoformat(),
            "total_budget": str(budget.total_amount),
            "currency": budget.currency,
            "categories": [
                {
                    "name": category.name,
                    "limit_amount": str(category.limit_amount),
                    "total_expenses": str(
                        repository.category_expense_total(
                            db,
                            budget.budget_id,
                            category.category_id,
                        )
                    ),
                }
                for category in categories
            ],
            "expenses": [
                {
                    "expense_id": str(expense.expense_id),
                    "category_id": str(expense.category_id),
                    "amount": str(expense.amount),
                    "occurred_at": expense.occurred_at.isoformat(),
                }
                for expense in expenses
            ],
        },
    )
    try:
        publish_event(event)
    except RabbitMQPublishError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ is temporarily unavailable.",
        ) from error


def build_budget_deleted_event(budget) -> dict:
    return new_event(
        "BudgetDeleted",
        {
            "user_id": str(budget.user_id),
            "budget_id": str(budget.budget_id),
            "period_start": budget.period_start.isoformat(),
        },
    )


def publish_budget_deleted(event: dict) -> None:
    try:
        publish_event(event)
    except RabbitMQPublishError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RabbitMQ is temporarily unavailable.",
        ) from error
