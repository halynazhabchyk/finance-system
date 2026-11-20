"""Writing events to the transactional outbox (published later by OutboxPublisher)."""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.models import OutboxEvent
from app.models.outbox_event import OUTBOX_PENDING

logger = logging.getLogger(__name__)


class SimulatedOutboxError(SQLAlchemyError):
    """Controlled failure used to demonstrate outbox atomicity (lab scenario)."""


def outbox_failure_simulated() -> bool:
    return os.getenv("OUTBOX_SIMULATE_FAILURE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def add_outbox_event(db, event: dict) -> OutboxEvent:
    """Stage an outbox row in the caller's transaction (no commit here)."""
    if outbox_failure_simulated():
        logger.warning(
            "OUTBOX_SIMULATE_FAILURE is enabled; failing outbox write for %s (%s).",
            event["event_id"],
            event["event_type"],
        )
        raise SimulatedOutboxError("Simulated outbox write failure.")
    saga_id = event.get("saga_id")
    item = OutboxEvent(
        id=uuid.UUID(event["event_id"]),
        aggregate_type=event["aggregate_type"],
        aggregate_id=uuid.UUID(event["aggregate_id"]),
        event_type=event["event_type"],
        payload=event,
        status=OUTBOX_PENDING,
        saga_id=uuid.UUID(saga_id) if saga_id else None,
    )
    db.add(item)
    return item
