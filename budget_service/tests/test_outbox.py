import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace


def test_outbox_event_preserves_envelope_identity():
    from app.integrations.outbox import add_outbox_event

    event_id = uuid.uuid4()
    aggregate_id = uuid.uuid4()
    event = {
        "event_id": str(event_id),
        "event_type": "BudgetUpdated",
        "aggregate_type": "Budget",
        "aggregate_id": str(aggregate_id),
        "aggregate_version": 2,
        "payload": "kept",
    }

    added = []

    class FakeSession:
        def add(self, item):
            added.append(item)

    result = add_outbox_event(FakeSession(), event)

    assert result.id == event_id
    assert result.aggregate_id == aggregate_id
    assert result.status == "PENDING"
    assert result.payload is event
    assert added == [result]


def test_expense_snapshot_uses_expense_aggregate_id(monkeypatch):
    from app.integrations import events

    budget_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    category_id = uuid.uuid4()
    budget = SimpleNamespace(
        budget_id=budget_id,
        user_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        total_amount=Decimal("100.00"),
        currency="UAH",
        aggregate_version=3,
    )
    expense = SimpleNamespace(
        expense_id=expense_id,
        category_id=category_id,
        amount=Decimal("10.00"),
        occurred_at=date(2026, 1, 2),
        description=None,
    )
    category = SimpleNamespace(
        category_id=category_id,
        name="Food",
        limit_amount=Decimal("50.00"),
    )
    monkeypatch.setattr(events.repository, "get_expenses", lambda db, _: [expense])
    monkeypatch.setattr(events.repository, "get_categories", lambda db, _: [category])
    monkeypatch.setattr(
        events.repository,
        "category_expense_total",
        lambda db, _, __: Decimal("10.00"),
    )

    event = events.build_budget_snapshot_event(
        object(),
        budget,
        "ExpenseCreated",
        aggregate_type="Expense",
        aggregate_id=expense_id,
    )

    assert event["event_type"] == "ExpenseCreated"
    assert event["aggregate_type"] == "Expense"
    assert event["aggregate_id"] == str(expense_id)
    assert event["expenses"][0]["expense_id"] == str(expense_id)


class FakeOutboxSession:
    """Minimal stand-in for a SQLAlchemy session used by OutboxPublisher."""

    def __init__(self, row=None):
        self.row = row
        self.commits = 0
        self.rollbacks = 0
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def scalar(self, statement):
        return self.row

    def execute(self, statement):
        self.executed.append(statement)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _pending_row():
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_type="ExpenseCreated",
        payload={"event_id": str(uuid.uuid4()), "event_type": "ExpenseCreated"},
        status="PENDING",
        published_at=None,
        publish_attempts=0,
        last_error=None,
    )


def test_outbox_publisher_marks_published_after_broker_confirm(monkeypatch):
    from app.workers import outbox_publisher

    row = _pending_row()
    session = FakeOutboxSession(row)
    published = []
    monkeypatch.setattr(outbox_publisher, "publish_event", published.append)

    publisher = outbox_publisher.OutboxPublisher(
        poll_interval=1,
        session_factory=lambda: session,
    )

    assert publisher.publish_pending_once() is True
    assert published == [row.payload]
    assert row.status == "PUBLISHED"
    assert row.published_at is not None
    assert row.publish_attempts == 1
    assert session.commits == 1


def test_outbox_publisher_keeps_pending_when_broker_unavailable(monkeypatch):
    from app.workers import outbox_publisher
    from shared.messaging.exceptions import RabbitMQPublishError

    row = _pending_row()
    sessions = [FakeOutboxSession(row), FakeOutboxSession()]

    def failing_publish(event):
        raise RabbitMQPublishError("broker is down")

    monkeypatch.setattr(outbox_publisher, "publish_event", failing_publish)
    publisher = outbox_publisher.OutboxPublisher(
        poll_interval=1,
        session_factory=lambda: sessions.pop(0) if len(sessions) > 1 else sessions[0],
    )

    assert publisher.publish_pending_once() is False
    assert row.status == "PENDING"
    assert row.published_at is None
    # The failure is recorded in a separate transaction (attempts + last_error).
    assert len(sessions[0].executed) == 1
    assert sessions[0].commits == 1


def test_outbox_publisher_returns_false_when_nothing_pending():
    from app.workers import outbox_publisher

    session = FakeOutboxSession(row=None)
    publisher = outbox_publisher.OutboxPublisher(
        poll_interval=1,
        session_factory=lambda: session,
    )

    assert publisher.publish_pending_once() is False
    assert session.rollbacks == 1


def test_outbox_write_failure_rolls_back_business_change(monkeypatch, db):
    import pytest

    from shared.errors import ServiceUnavailableError
    from app.services import common, expenses

    monkeypatch.setenv("OUTBOX_SIMULATE_FAILURE", "true")
    budget = SimpleNamespace(
        budget_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        aggregate_version=1,
    )
    expense = SimpleNamespace(expense_id=uuid.uuid4())
    monkeypatch.setattr(expenses, "budget_or_404", lambda *args, **kwargs: budget)
    monkeypatch.setattr(expenses.repository, "get_category", lambda *args: object())
    monkeypatch.setattr(expenses.repository, "create_expense", lambda *args, **kwargs: expense)
    monkeypatch.setattr(
        common,
        "build_budget_snapshot_event",
        lambda *args, **kwargs: {
            "event_id": str(uuid.uuid4()),
            "event_type": "ExpenseCreated",
            "aggregate_type": "Expense",
            "aggregate_id": str(expense.expense_id),
        },
    )
    payload = SimpleNamespace(
        category_id=uuid.uuid4(),
        occurred_at=date(2026, 1, 2),
        model_dump=lambda: {},
    )

    with pytest.raises(ServiceUnavailableError):
        expenses.create_expense(db, uuid.uuid4(), uuid.uuid4(), payload)

    assert db.rollbacks == 1
    assert db.commits == 0
    # The saga row was staged in the same session and is discarded by rollback.
    assert [type(item).__name__ for item in db.added] == ["SagaInstance"]


def test_snapshot_rejects_unknown_event_type():
    import pytest

    from app.integrations import events

    with pytest.raises(ValueError):
        events.build_budget_snapshot_event(
            object(),
            SimpleNamespace(budget_id=uuid.uuid4()),
            "BudgetSnapshotChanged",
        )
