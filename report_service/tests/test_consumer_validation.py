"""Step 1 of ReportEventConsumer: reject malformed messages before the database."""

import uuid

import pytest

from factories import make_event, without


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(make_event("BudgetSnapshotChanged"), id="unknown-type"),
        pytest.param(make_event("ExpenseCreated", event_version=2), id="unsupported-version"),
        pytest.param(make_event("ExpenseCreated", event_id="not-a-uuid"), id="invalid-event-id"),
        pytest.param(without(make_event("ExpenseCreated"), "event_id"), id="missing-event-id"),
        pytest.param(
            without(make_event("ExpenseUpdated"), "aggregate_version"),
            id="budget-missing-field",
        ),
        pytest.param(
            make_event("ExpenseCreated", saga_id=str(uuid.uuid4())),
            id="saga-missing-expense-id",
        ),
        pytest.param(
            without(make_event("MonthlyReportUpdateRequested"), "period_end"),
            id="scheduler-missing-field",
        ),
    ],
)
def test_malformed_event_is_rejected_before_opening_session(consumer_env, event):
    from shared.messaging.exceptions import PermanentEventError

    module, session, calls = consumer_env

    with pytest.raises(PermanentEventError):
        module.ReportEventConsumer().handle(event)
    assert calls["sessions"] == 0
    assert session.rollbacks == 0
    assert session.commits == 0
    assert calls["processed"] == []


def test_consumer_binds_lr2_routing_keys():
    from app.workers import report_consumer

    consumer = report_consumer.ReportEventConsumer()._consumer

    assert consumer.queue_name == "report-service-events"
    assert {
        "BudgetCreated",
        "BudgetUpdated",
        "BudgetDeleted",
        "ExpenseCreated",
        "ExpenseUpdated",
        "ExpenseDeleted",
        "ExpenseCancelled",
        "DailyReportUpdateRequested",
        "MonthlyReportUpdateRequested",
    } == set(consumer.routing_keys)
