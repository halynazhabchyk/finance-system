"""Step 2 of ReportEventConsumer: apply each event once (Transactional Inbox)."""

import uuid
from datetime import date, datetime, timezone

import pytest

from factories import make_event


@pytest.mark.parametrize(
    "event_type",
    [
        "BudgetCreated",
        "BudgetUpdated",
        "ExpenseCreated",
        "ExpenseUpdated",
        "ExpenseDeleted",
        "ExpenseCancelled",
    ],
)
def test_lr2_budget_events_apply_snapshot(consumer_env, event_type):
    module, session, calls = consumer_env

    module.ReportEventConsumer().handle(make_event(event_type))

    assert calls["snapshot"] == [event_type]
    assert len(calls["processed"]) == 1
    assert session.commits == 1


def test_budget_deleted_removes_report(consumer_env):
    module, session, calls = consumer_env

    module.ReportEventConsumer().handle(make_event("BudgetDeleted", aggregate_type="Budget"))

    assert calls["deleted"] == ["BudgetDeleted"]
    assert session.commits == 1


def test_scheduler_event_refreshes_reports_with_parsed_values(consumer_env):
    module, session, calls = consumer_env

    module.ReportEventConsumer().handle(make_event("MonthlyReportUpdateRequested"))

    assert calls["refresh"] == [
        (datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc), date(2026, 1, 1), date(2026, 1, 31))
    ]
    assert calls["snapshot"] == []
    assert len(calls["processed"]) == 1
    assert session.commits == 1


def test_inbox_row_stores_type_and_receive_time(consumer_env, monkeypatch):
    module, session, calls = consumer_env
    stored = []
    monkeypatch.setattr(
        module.repository,
        "mark_event_processed",
        lambda db, event_id, event_type, received_at: stored.append(
            (event_id, event_type, received_at)
        ),
    )
    event = make_event("ExpenseUpdated")

    module.ReportEventConsumer().handle(event)

    assert stored[0][0] == uuid.UUID(event["event_id"])
    assert stored[0][1] == "ExpenseUpdated"
    assert stored[0][2].tzinfo is not None


def test_duplicate_event_is_not_applied_twice(consumer_env):
    module, session, calls = consumer_env
    event = make_event("ExpenseCreated")
    consumer = module.ReportEventConsumer()

    consumer.handle(event)
    consumer.handle(event)

    assert calls["snapshot"] == ["ExpenseCreated"]
    assert len(calls["processed"]) == 1
    assert session.commits == 1  # the duplicate is rolled back, not committed
    assert session.rollbacks == 1
    assert session.closed


def test_failed_processing_does_not_mark_event_processed(consumer_env, monkeypatch):
    module, session, calls = consumer_env

    def broken(db, event):
        raise RuntimeError("read model write failed")

    monkeypatch.setattr(module.repository, "apply_budget_snapshot", broken)

    with pytest.raises(RuntimeError):
        module.ReportEventConsumer().handle(make_event("ExpenseCreated"))
    assert calls["processed"] == []
    assert session.rollbacks == 1
    assert session.commits == 0
