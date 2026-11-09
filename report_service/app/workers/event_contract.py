"""Events consumed by Report Service and validation of incoming messages."""

from __future__ import annotations

import uuid

from shared.messaging.exceptions import PermanentEventError

QUEUE_NAME = "report-service-events"
SUPPORTED_EVENT_VERSION = 1

# Budget Service events (LR2 contract + ExpenseCancelled) carry a full budget
# snapshot with aggregate_version, so they share one idempotent handler.
BUDGET_SNAPSHOT_EVENTS = frozenset(
    {
        "BudgetCreated",
        "BudgetUpdated",
        "ExpenseCreated",
        "ExpenseUpdated",
        "ExpenseDeleted",
        "ExpenseCancelled",
    }
)
BUDGET_DELETED_EVENT = "BudgetDeleted"
BUDGET_EVENTS = BUDGET_SNAPSHOT_EVENTS | {BUDGET_DELETED_EVENT}
SCHEDULER_EVENTS = frozenset({"DailyReportUpdateRequested", "MonthlyReportUpdateRequested"})
SUPPORTED_EVENTS = BUDGET_EVENTS | SCHEDULER_EVENTS

BUDGET_REQUIRED_FIELDS = frozenset({"aggregate_id", "aggregate_version", "user_id", "period_start"})
SAGA_REQUIRED_FIELDS = frozenset({"expense_id", "budget_id"})
SCHEDULER_REQUIRED_FIELDS = frozenset({"created_at", "period_start", "period_end"})


def validate_event(event: dict) -> None:
    """Raise PermanentEventError for a message that no retry can fix.

    Runs before a database session is opened, so a malformed message never
    touches the inbox and goes straight to the DLQ (see EventConsumer).
    """
    version = event.get("event_version")
    if version != SUPPORTED_EVENT_VERSION:
        raise PermanentEventError(f"Unsupported event version: {version}")

    try:
        uuid.UUID(str(event["event_id"]))
    except (KeyError, ValueError) as exc:
        raise PermanentEventError(f"Invalid event_id: {event.get('event_id')}") from exc

    event_type = event.get("event_type")
    if event_type not in SUPPORTED_EVENTS:
        raise PermanentEventError(f"Unsupported event type: {event_type}")

    missing = _required_fields(event, event_type).difference(event)
    if missing:
        source = "Budget" if event_type in BUDGET_EVENTS else "Scheduler"
        raise PermanentEventError(f"{source} event is missing fields: {sorted(missing)}")


def _required_fields(event: dict, event_type: str) -> frozenset[str]:
    if event_type in SCHEDULER_EVENTS:
        return SCHEDULER_REQUIRED_FIELDS
    if event.get("saga_id"):
        return BUDGET_REQUIRED_FIELDS | SAGA_REQUIRED_FIELDS
    return BUDGET_REQUIRED_FIELDS
