"""Report Service as the second participant of the "create expense" SAGA.

It applies ExpenseCreated (T2) and replies with ExpenseProcessed; it applies
ExpenseCancelled from Budget Service as its compensation (CT2).
"""

from __future__ import annotations

import os
import uuid

from shared.contracts.events import new_event

SAGA_STEP_EVENT = "ExpenseCreated"
SAGA_REPLY_EVENT = "ExpenseProcessed"
# Fixed namespace: the reply event_id must stay the same for one saga, so
# Budget Service can detect a repeated reply. Do not change it.
SAGA_REPLY_NAMESPACE = uuid.UUID("6f1c2d3e-4b5a-4c7d-8e9f-0a1b2c3d4e5f")


class SimulatedProcessingError(RuntimeError):
    """Controlled failure of the consumer's local transaction (lab scenario)."""


def processing_failure_simulated() -> bool:
    return os.getenv("REPORT_SIMULATE_FAILURE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def is_saga_step(event: dict) -> bool:
    """ExpenseCreated that belongs to a SAGA and therefore needs a reply."""
    return event.get("event_type") == SAGA_STEP_EVENT and bool(event.get("saga_id"))


def raise_if_failure_simulated(event: dict) -> None:
    """Lab scenario B: fail after the read-model write but before COMMIT.

    Only the SAGA step fails, so compensation (ExpenseCancelled) still
    gets through while the simulation is on.
    """
    if is_saga_step(event) and processing_failure_simulated():
        raise SimulatedProcessingError(
            f"Simulated failure while processing {event['event_type']} "
            f"{event['event_id']} (saga {event['saga_id']})."
        )


def build_saga_reply(event: dict) -> dict:
    """ExpenseProcessed for one saga; a stable event_id makes repeats detectable."""
    return new_event(
        SAGA_REPLY_EVENT,
        {
            "saga_id": event["saga_id"],
            "expense_id": event["expense_id"],
            "budget_id": event["budget_id"],
            "causation_event_id": event["event_id"],
        },
        event_id=str(uuid.uuid5(SAGA_REPLY_NAMESPACE, f"{SAGA_REPLY_EVENT}:{event['saga_id']}")),
        aggregate_type="Expense",
        aggregate_id=event["expense_id"],
    )
