"""RabbitMQ worker that updates the Report Service read model.

Each message goes through three steps (see ``ReportEventConsumer.handle``):

1. validate   - reject a malformed message before touching the database
                (``event_contract``);
2. apply once - one local transaction: inbox check, read-model change,
                inbox row, COMMIT (Transactional Inbox);
3. reply      - for the "create expense" SAGA step, publish ExpenseProcessed
                after COMMIT (``saga_participant``).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from shared.messaging.consumer import EventConsumer
from shared.messaging.publisher import publish_event

from app.db.session import SessionLocal
from app.repositories import reports as repository
from app.workers.event_contract import (
    BUDGET_DELETED_EVENT,
    BUDGET_SNAPSHOT_EVENTS,
    QUEUE_NAME,
    SCHEDULER_EVENTS,
    SUPPORTED_EVENTS,
    validate_event,
)
from app.workers.saga_participant import (
    SAGA_REPLY_EVENT,
    SimulatedProcessingError,
    build_saga_reply,
    is_saga_step,
    raise_if_failure_simulated,
)

__all__ = ["ReportEventConsumer", "SimulatedProcessingError"]

logger = logging.getLogger(__name__)

Applier = Callable[[Session, dict], None]


class ReportEventConsumer:
    """Consume Budget and Scheduler events with transactional acknowledgements."""

    def __init__(self) -> None:
        self._consumer = EventConsumer(
            queue_name=QUEUE_NAME,
            routing_keys=sorted(SUPPORTED_EVENTS),
            handler=self.handle,
        )
        self._appliers: dict[str, Applier] = {
            BUDGET_DELETED_EVENT: self._apply_budget_deleted,
            **{event_type: self._apply_snapshot for event_type in BUDGET_SNAPSHOT_EVENTS},
            **{event_type: self._refresh_reports for event_type in SCHEDULER_EVENTS},
        }

    def start(self) -> None:
        self._consumer.start()

    def stop(self) -> None:
        self._consumer.stop()

    def handle(self, event: dict) -> None:
        """Process one message. An exception means "not done": EventConsumer retries."""
        validate_event(event)
        self._apply_once(event)
        if is_saga_step(event):
            # Also sent for a duplicate: the first reply may have been lost.
            self._reply(event)

    # --- Step 2: local transaction (Transactional Inbox) ---------------------

    def _apply_once(self, event: dict) -> None:
        """Apply the event to the read model at most once.

        The read-model change and the inbox row are committed together, so
        after a failure neither of them is stored and redelivery is safe.
        """
        event_id = uuid.UUID(event["event_id"])
        event_type = event["event_type"]
        received_at = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            if repository.event_processed(db, event_id):
                db.rollback()
                logger.info(
                    "Skipping duplicate event %s (%s): already in processed_events.",
                    event_id,
                    event_type,
                )
                return

            self._appliers[event_type](db, event)
            raise_if_failure_simulated(event)
            repository.mark_event_processed(db, event_id, event_type, received_at)
            db.commit()
            logger.info("Processed event %s (%s).", event_id, event_type)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _apply_snapshot(db: Session, event: dict) -> None:
        repository.apply_budget_snapshot(db, event)

    @staticmethod
    def _apply_budget_deleted(db: Session, event: dict) -> None:
        repository.apply_budget_deleted(db, event)

    @staticmethod
    def _refresh_reports(db: Session, event: dict) -> None:
        repository.refresh_reports(
            db,
            datetime.fromisoformat(event["created_at"]).astimezone(timezone.utc),
            date.fromisoformat(event["period_start"]),
            date.fromisoformat(event["period_end"]),
        )

    # --- Step 3: SAGA reply ---------------------------------------------------

    @staticmethod
    def _reply(event: dict) -> None:
        """Publish ExpenseProcessed after COMMIT; a failure triggers redelivery."""
        reply = build_saga_reply(event)
        publish_event(reply)
        logger.info(
            "Published %s %s for saga %s (expense %s).",
            SAGA_REPLY_EVENT,
            reply["event_id"],
            event["saga_id"],
            event["expense_id"],
        )
