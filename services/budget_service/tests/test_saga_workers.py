import uuid
from types import SimpleNamespace

import pytest


class Ctx:
    def __init__(self):
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def rollback(self):
        self.rollbacks += 1


def test_reply_consumer_listens_for_expense_processed():
    from app.workers.saga_reply_consumer import SagaReplyConsumer

    consumer = SagaReplyConsumer()._consumer

    assert consumer.queue_name == "budget-service-saga-events"
    assert consumer.routing_keys == ["ExpenseProcessed"]
    assert consumer.exchange == "finance.events"
    assert consumer.use_retry_topology is False


def test_reply_consumer_confirms_saga():
    from app.workers.saga_reply_consumer import SagaReplyConsumer

    confirmed = []
    service = SimpleNamespace(confirm=lambda db, saga_id: confirmed.append(saga_id))
    saga_id = uuid.uuid4()

    SagaReplyConsumer(session_factory=Ctx, service=service).handle(
        {"event_type": "ExpenseProcessed", "event_id": "x", "saga_id": str(saga_id)}
    )

    assert confirmed == [saga_id]


def test_reply_without_saga_id_is_permanent_error():
    from app.workers.saga_reply_consumer import SagaReplyConsumer
    from shared.messaging.exceptions import PermanentEventError

    with pytest.raises(PermanentEventError):
        SagaReplyConsumer(session_factory=Ctx, service=SimpleNamespace()).handle(
            {"event_type": "ExpenseProcessed"}
        )


def test_dlq_consumer_binds_copy_queue_to_dead_letter_exchange():
    from app.workers.saga_dlq_consumer import SagaDlqConsumer

    consumer = SagaDlqConsumer(handler=SimpleNamespace())._consumer

    assert consumer.queue_name == "budget-service-saga-dlq"
    assert consumer.exchange == "finance.events.dlx"
    assert consumer.routing_keys == ["ExpenseCreated"]
    assert consumer.use_retry_topology is False


def test_dlq_consumer_compensates_with_dlq_reason():
    from app.workers.saga_dlq_consumer import SagaDlqConsumer

    calls = []
    handler = SimpleNamespace(
        compensate=lambda saga_id, reason, details, **kw: calls.append((saga_id, reason))
    )
    saga_id = uuid.uuid4()

    SagaDlqConsumer(handler=handler).handle(
        {"event_type": "ExpenseCreated", "event_id": "e1", "saga_id": str(saga_id)}
    )

    assert calls == [(saga_id, "DLQ")]


def test_dlq_consumer_ignores_expense_created_without_saga():
    from app.workers.saga_dlq_consumer import SagaDlqConsumer

    calls = []
    handler = SimpleNamespace(compensate=lambda *a, **k: calls.append(a))

    SagaDlqConsumer(handler=handler).handle({"event_type": "ExpenseCreated", "event_id": "e1"})

    assert calls == []


def test_timeout_watcher_compensates_overdue_sagas(monkeypatch):
    from app.workers import saga_timeout_watcher as module

    overdue = [uuid.uuid4(), uuid.uuid4()]
    monkeypatch.setattr(
        module.saga_repository,
        "find_sagas_needing_compensation",
        lambda db, now, limit: overdue,
    )
    calls = []

    def compensate(saga_id, reason, details, *, skip_locked=False):
        calls.append((saga_id, reason, skip_locked))
        if saga_id == overdue[1]:
            raise RuntimeError("temporary failure")
        return True

    watcher = module.SagaTimeoutWatcher(
        interval=1,
        session_factory=Ctx,
        handler=SimpleNamespace(compensate=compensate),
    )

    assert watcher.check_once() == 1
    assert calls == [(overdue[0], "TIMEOUT", True), (overdue[1], "TIMEOUT", True)]

