"""Consumes ExpenseProcessed replies from Report Service and completes sagas."""

from __future__ import annotations

import logging
import uuid

from shared.messaging.config import rabbitmq_exchange
from shared.messaging.consumer import EventConsumer
from shared.messaging.exceptions import PermanentEventError

from app.db.session import SessionLocal
from app.services.saga import SagaService

logger = logging.getLogger(__name__)

SAGA_REPLY_QUEUE = "budget-service-saga-events"
SAGA_REPLY_EVENT = "ExpenseProcessed"


class SagaReplyConsumer:
    def __init__(self, session_factory=None, service: SagaService | None = None) -> None:
        self.session_factory = session_factory or SessionLocal
        self.service = service or SagaService()
        self._consumer = EventConsumer(
            queue_name=SAGA_REPLY_QUEUE,
            routing_keys=[SAGA_REPLY_EVENT],
            handler=self.handle,
            exchange=rabbitmq_exchange(),
            use_retry_topology=False,
            thread_name="saga-reply-consumer",
        )

    def start(self) -> None:
        self._consumer.start()

    def stop(self) -> None:
        self._consumer.stop()

    def handle(self, event: dict) -> None:
        if event.get("event_type") != SAGA_REPLY_EVENT or not event.get("saga_id"):
            raise PermanentEventError("ExpenseProcessed without saga_id.")
        try:
            saga_id = uuid.UUID(event["saga_id"])
        except ValueError as error:
            raise PermanentEventError("Invalid saga_id.") from error
        logger.info(
            "SagaReplyConsumer received ExpenseProcessed %s for saga %s.",
            event.get("event_id"),
            saga_id,
        )
        # confirm() commits or rolls back itself; it is idempotent (8.7).
        with self.session_factory() as db:
            self.service.confirm(db, saga_id)
