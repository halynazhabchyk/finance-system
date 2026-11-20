"""T1 of the "create expense" SAGA and the HTTP view of its state."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest


def test_saga_start_sets_deadline_from_timeout(monkeypatch, db):
    from app.models import SagaInstance
    from app.services.saga import SagaService

    monkeypatch.setenv("SAGA_TIMEOUT_SECONDS", "30")
    expense_id = uuid.uuid4()

    saga = SagaService().start_create_expense(db, expense_id)

    assert isinstance(saga, SagaInstance)
    assert db.added == [saga]
    assert saga.status == "STARTED"
    assert saga.saga_type == "CreateExpense"
    assert saga.aggregate_type == "Expense"
    assert saga.aggregate_id == expense_id
    assert saga.deadline_at - saga.started_at == timedelta(seconds=30)
    assert saga.finished_at is None


def test_create_expense_starts_saga_in_same_transaction(monkeypatch, db):
    from app.services import common, expenses

    budget = SimpleNamespace(
        budget_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        aggregate_version=4,
    )
    created = {}
    expense = SimpleNamespace(expense_id=uuid.uuid4())

    def create_expense(db, budget_id, **values):
        created.update(values)
        return expense

    captured = {}

    def build_event(db, budget, event_type, **kwargs):
        captured["event_type"] = event_type
        captured.update(kwargs)
        return {"event_type": event_type, **kwargs["extra"]}

    outbox = []
    monkeypatch.setattr(expenses, "budget_or_404", lambda *a, **k: budget)
    monkeypatch.setattr(expenses.repository, "get_category", lambda *a: object())
    monkeypatch.setattr(expenses.repository, "create_expense", create_expense)
    monkeypatch.setattr(common, "build_budget_snapshot_event", build_event)
    monkeypatch.setattr(common, "add_outbox_event", lambda db, event: outbox.append(event))
    payload = SimpleNamespace(
        category_id=uuid.uuid4(),
        occurred_at=date(2026, 1, 2),
        model_dump=lambda: {"amount": Decimal("10.00")},
    )

    result = expenses.create_expense(db, uuid.uuid4(), uuid.uuid4(), payload)

    assert result is expense
    assert created["saga_status"] == "PENDING"
    assert budget.aggregate_version == 5
    saga = db.added[0]
    assert saga.aggregate_id == expense.expense_id
    assert captured["event_type"] == "ExpenseCreated"
    assert outbox[0]["saga_id"] == str(saga.saga_id)
    assert outbox[0]["expense_id"] == str(expense.expense_id)
    assert db.commits == 1


@pytest.mark.parametrize("status", ["PENDING", "CANCELLED"])
def test_not_confirmed_expense_cannot_be_changed(monkeypatch, db, status):
    from shared.errors import ConflictError
    from app.services import expenses

    expense = SimpleNamespace(saga_status=status)
    monkeypatch.setattr(expenses, "budget_or_404", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(expenses.repository, "get_expense", lambda *a: expense)

    with pytest.raises(ConflictError):
        expenses.delete_expense(db, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

    assert db.rollbacks == 1
    assert db.deleted == []


def test_totals_exclude_cancelled_expenses():
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models import Expense
    from app.repositories.budgets import _active

    sql = str(_active(select(Expense)).compile(dialect=postgresql.dialect()))

    assert "expenses.saga_status !=" in sql


def test_saga_endpoint_returns_contract(client, as_user, monkeypatch):
    from app.api.routers import expenses as router_module

    now = datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc)
    saga = SimpleNamespace(
        saga_id=uuid.uuid4(),
        saga_type="CreateExpense",
        aggregate_type="Expense",
        aggregate_id=uuid.uuid4(),
        status="CANCELLED",
        current_step="EXPENSE_CANCELLED",
        started_at=now,
        deadline_at=now + timedelta(seconds=30),
        finished_at=now + timedelta(seconds=31),
        failure_reason="TIMEOUT",
        failure_details="No ExpenseProcessed before deadline.",
        compensation_attempts=1,
        last_error=None,
    )
    monkeypatch.setattr(router_module.expense_service, "get_expense_saga", lambda *a: saga)
    as_user(uuid.uuid4())

    response = client.get(f"/internal/budgets/{uuid.uuid4()}/expenses/{saga.aggregate_id}/saga")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["failure_reason"] == "TIMEOUT"
    assert body["saga_type"] == "CreateExpense"
