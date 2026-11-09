"""SAGA state transitions: confirmation (C) and compensation (CT1)."""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest


@pytest.fixture
def saga_world(monkeypatch):
    """One STARTED saga for one PENDING expense, wired into fake repositories."""
    from app.repositories import budgets as budget_repository
    from app.repositories import sagas as saga_repository
    from app.services import common
    from app.services import saga as saga_package

    expense_id = uuid.uuid4()
    budget = SimpleNamespace(budget_id=uuid.uuid4(), aggregate_version=3)
    expense = SimpleNamespace(
        expense_id=expense_id,
        budget_id=budget.budget_id,
        category_id=uuid.uuid4(),
        amount=Decimal("250.00"),
        occurred_at=date(2026, 1, 5),
        description=None,
        saga_status="PENDING",
    )
    saga = SimpleNamespace(
        saga_id=uuid.uuid4(),
        aggregate_id=expense_id,
        status="STARTED",
        current_step="EXPENSE_CREATED",
        failure_reason=None,
        failure_details=None,
        compensation_attempts=0,
        finished_at=None,
        last_error=None,
    )
    outbox = []
    monkeypatch.setattr(saga_repository, "get_saga", lambda db, sid, **k: saga)
    monkeypatch.setattr(budget_repository, "get_expense_by_id", lambda db, eid, **k: expense)
    monkeypatch.setattr(budget_repository, "get_budget", lambda db, bid, **k: budget)
    monkeypatch.setattr(
        common,
        "build_budget_snapshot_event",
        lambda db, budget, event_type, **kwargs: {
            "event_type": event_type,
            "aggregate_version": budget.aggregate_version,
            **kwargs["extra"],
        },
    )
    monkeypatch.setattr(common, "add_outbox_event", lambda db, event: outbox.append(event))
    return SimpleNamespace(
        saga=saga_package,
        common=common,
        record=saga,
        expense=expense,
        budget=budget,
        outbox=outbox,
    )


def test_confirm_completes_saga_and_confirms_expense(saga_world, db):
    assert saga_world.saga.SagaService().confirm(db, saga_world.record.saga_id) is True

    assert saga_world.record.status == "COMPLETED"
    assert saga_world.record.current_step == "REPORT_CONFIRMED"
    assert saga_world.record.finished_at is not None
    assert saga_world.expense.saga_status == "CONFIRMED"
    assert db.commits == 1


def test_late_confirmation_does_not_change_cancelled_saga(saga_world, db):
    saga_world.record.status = "CANCELLED"
    saga_world.expense.saga_status = "CANCELLED"

    assert saga_world.saga.SagaService().confirm(db, saga_world.record.saga_id) is False

    assert saga_world.record.status == "CANCELLED"
    assert saga_world.expense.saga_status == "CANCELLED"
    assert db.commits == 0


def test_cancel_expense_compensates_and_queues_expense_cancelled(saga_world, db):
    result = saga_world.saga.cancel_expense(
        db,
        saga_world.record.saga_id,
        "DLQ",
        "ExpenseCreated reached DLQ.",
    )

    assert result is True
    assert saga_world.expense.saga_status == "CANCELLED"
    assert saga_world.budget.aggregate_version == 4
    assert saga_world.record.status == "CANCELLED"
    assert saga_world.record.failure_reason == "DLQ"
    assert saga_world.record.finished_at is not None
    assert [event["event_type"] for event in saga_world.outbox] == ["ExpenseCancelled"]
    event = saga_world.outbox[0]
    assert event["saga_id"] == str(saga_world.record.saga_id)
    assert event["cancellation_reason"] == "DLQ"
    assert event["cancelled_expense"]["amount"] == "250.00"
    assert db.commits == 1


def test_repeated_compensation_does_not_change_data_again(saga_world, session_factory):
    saga_world.saga.cancel_expense(session_factory(), saga_world.record.saga_id, "DLQ", "first")
    version_after_first = saga_world.budget.aggregate_version

    second = session_factory()
    result = saga_world.saga.cancel_expense(second, saga_world.record.saga_id, "TIMEOUT", "second")

    assert result is False
    assert saga_world.budget.aggregate_version == version_after_first
    assert len(saga_world.outbox) == 1
    assert saga_world.record.failure_reason == "DLQ"
    assert second.commits == 0


def test_compensation_is_skipped_for_completed_saga(saga_world, db):
    saga_world.record.status = "COMPLETED"
    saga_world.expense.saga_status = "CONFIRMED"

    result = saga_world.saga.cancel_expense(db, saga_world.record.saga_id, "TIMEOUT", "late")

    assert result is False
    assert saga_world.expense.saga_status == "CONFIRMED"
    assert saga_world.outbox == []


def test_compensation_closes_saga_when_expense_is_gone(saga_world, monkeypatch, db):
    from app.repositories import budgets as budget_repository

    monkeypatch.setattr(budget_repository, "get_expense_by_id", lambda db, eid, **k: None)

    assert saga_world.saga.cancel_expense(db, saga_world.record.saga_id, "TIMEOUT", "gone.") is True

    assert saga_world.record.status == "CANCELLED"
    assert saga_world.record.failure_details.endswith("Expense no longer exists.")
    assert saga_world.outbox == []


def test_failed_compensation_is_recorded_for_retry(saga_world, monkeypatch, session_factory):
    def broken_outbox(db, event):
        raise RuntimeError("database went away")

    monkeypatch.setattr(saga_world.common, "add_outbox_event", broken_outbox)
    handler = saga_world.saga.CompensationHandler(session_factory)

    with pytest.raises(RuntimeError):
        handler.compensate(saga_world.record.saga_id, "DLQ", "ExpenseCreated reached DLQ.")

    sessions = session_factory.sessions
    # mark_compensating, failed cancel (rolled back), failure record.
    assert len(sessions) == 3
    assert saga_world.record.status == "COMPENSATING"
    assert sessions[1].rollbacks >= 1
    assert len(sessions[2].executed) == 1
    assert sessions[2].commits == 1
