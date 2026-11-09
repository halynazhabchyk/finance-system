"""Step 3 of ReportEventConsumer: Report Service as a participant of the SAGA."""

import pytest

from factories import saga_event


def test_saga_step_replies_expense_processed_after_commit(consumer_env, replies):
    module, session, calls = consumer_env
    event = saga_event()

    module.ReportEventConsumer().handle(event)

    assert session.commits == 1
    assert len(replies) == 1
    reply = replies[0]
    assert reply["event_type"] == "ExpenseProcessed"
    assert reply["saga_id"] == event["saga_id"]
    assert reply["expense_id"] == event["expense_id"]
    assert reply["causation_event_id"] == event["event_id"]


def test_simulated_failure_rolls_back_consumer_transaction(consumer_env, replies, monkeypatch):
    module, session, calls = consumer_env
    monkeypatch.setenv("REPORT_SIMULATE_FAILURE", "true")

    with pytest.raises(module.SimulatedProcessingError):
        module.ReportEventConsumer().handle(saga_event())

    assert calls["snapshot"] == ["ExpenseCreated"]  # written, then rolled back
    assert calls["processed"] == []
    assert session.commits == 0
    assert session.rollbacks == 1
    assert replies == []


def test_simulated_failure_does_not_block_compensation(consumer_env, replies, monkeypatch):
    module, session, calls = consumer_env
    monkeypatch.setenv("REPORT_SIMULATE_FAILURE", "true")

    module.ReportEventConsumer().handle(saga_event("ExpenseCancelled"))

    assert calls["snapshot"] == ["ExpenseCancelled"]
    assert session.commits == 1
    assert replies == []


def test_duplicate_saga_step_repeats_reply_without_reapplying(consumer_env, replies):
    module, session, calls = consumer_env
    event = saga_event()
    consumer = module.ReportEventConsumer()

    consumer.handle(event)
    consumer.handle(event)

    assert calls["snapshot"] == ["ExpenseCreated"]
    assert len(replies) == 2
    assert replies[0]["event_id"] == replies[1]["event_id"]


def test_reply_failure_keeps_committed_result_and_requests_redelivery(consumer_env, monkeypatch):
    from shared.messaging.exceptions import RabbitMQPublishError

    module, session, calls = consumer_env

    def down(event):
        raise RabbitMQPublishError("broker is down")

    monkeypatch.setattr(module, "publish_event", down)

    with pytest.raises(RabbitMQPublishError):
        module.ReportEventConsumer().handle(saga_event())

    assert session.commits == 1
    assert len(calls["processed"]) == 1
