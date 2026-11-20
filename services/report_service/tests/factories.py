"""Builders of RabbitMQ event dictionaries for consumer tests."""

import uuid


def make_event(event_type, **extra):
    event = {
        "event_id": str(uuid.uuid4()),
        "event_version": 1,
        "event_type": event_type,
        "created_at": "2026-01-02T10:00:00+00:00",
        "aggregate_type": "Expense",
        "aggregate_id": str(uuid.uuid4()),
        "aggregate_version": 2,
        "user_id": str(uuid.uuid4()),
        "budget_id": str(uuid.uuid4()),
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
    }
    event.update(extra)
    return event


def saga_event(event_type="ExpenseCreated"):
    """An event that belongs to the "create expense" SAGA."""
    return make_event(event_type, saga_id=str(uuid.uuid4()), expense_id=str(uuid.uuid4()))


def without(event, *fields):
    return {key: value for key, value in event.items() if key not in fields}
