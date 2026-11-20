"""Starts compensation when ExpenseCreated is dead-lettered by Report Service."""

from __future__ import annotations

import logging
import uuid

from shared.messaging.config import rabbitmq_exchange
from shared.messaging.consumer import EventConsumer
from shared.messaging.exceptions import PermanentEventError

from app.db.session import SessionLocal
from app.models.saga_instance import REASON_DLQ
from app.services.saga import CompensationHandler

logger = logging.getLogger(__name__)

SAGA_DLQ_QUEUE = "budget-service-saga-dlq"
SAGA_STEP_EVENT = "ExpenseCreated"


def dead_letter_exchange() -> str:
    return f"{rabbitmq_exchange()}.dlx"


class SagaDlqConsumer:
    def __init__(self, handler: CompensationHandler | None = None) -> None:
        self.handler = handler or CompensationHandler(SessionLocal)
        self._consumer = EventConsumer(
            queue_name=SAGA_DLQ_QUEUE,
            routing_keys=[SAGA_STEP_EVENT],
            handler=self.handle,
            exchange=dead_letter_exchange(),
            use_retry_topology=False,
            thread_name="saga-dlq-consumer",
        )

    def start(self) -> None:
        self._consumer.start()

    def stop(self) -> None:
        self._consumer.stop()

    def handle(self, event: dict) -> None:
        if event.get("event_type") != SAGA_STEP_EVENT:
            raise PermanentEventError(f"Unexpected DLQ event {event.get('event_type')}.")
        if not event.get("saga_id"):
            logger.info(
                "Dead-lettered ExpenseCreated %s has no saga_id; nothing to compensate.",
                event.get("event_id"),
            )
            return
        try:
            saga_id = uuid.UUID(event["saga_id"])
        except ValueError as error:
            raise PermanentEventError("Invalid saga_id.") from error
        logger.warning(
            "SagaDlqConsumer received dead-lettered ExpenseCreated %s for saga %s; compensating.",
            event.get("event_id"),
            saga_id,
        )
        # On failure the message is requeued.
        self.handler.compensate(
            saga_id,
            REASON_DLQ,
            f"ExpenseCreated {event.get('event_id')} reached the dead-letter queue "
            "after the configured delivery attempts.",
        )
