"""Asynchronous worker that publishes Budget Service outbox events."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.models import OutboxEvent
from app.models.outbox_event import OUTBOX_PENDING, OUTBOX_PUBLISHED
from shared.messaging.publisher import publish_event

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000


class OutboxPublisher:
    """Polling publisher: moves PENDING outbox rows to RabbitMQ in creation order."""

    def __init__(self, poll_interval: float | None = None, session_factory=None) -> None:
        self.poll_interval = poll_interval or float(
            os.getenv("OUTBOX_POLL_INTERVAL", "2")
        )
        self.session_factory = session_factory or SessionLocal

    def publish_pending_once(self) -> bool:
        """Publish the oldest available event, retaining the row lock until commit.

        Returns True when an event was published, so the caller can continue
        without waiting for the next poll interval.
        """
        with self.session_factory() as db:
            event = db.scalar(
                select(OutboxEvent)
                .where(OutboxEvent.status == OUTBOX_PENDING)
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if event is None:
                db.rollback()
                return False
            event_id = event.id
            event_type = event.event_type
            try:
                publish_event(event.payload)
                event.status = OUTBOX_PUBLISHED
                event.published_at = datetime.now(timezone.utc)
                event.publish_attempts += 1
                event.last_error = None
                db.commit()
            except Exception as error:
                db.rollback()
                logger.exception(
                    "Could not publish outbox event %s (%s); it remains PENDING.",
                    event_id,
                    event_type,
                )
                self._record_failure(event_id, error)
                return False
        logger.info("Outbox event %s (%s) marked PUBLISHED.", event_id, event_type)
        return True

    def _record_failure(self, event_id, error: Exception) -> None:
        """Store diagnostics in a separate transaction; the row stays PENDING."""
        try:
            with self.session_factory() as db:
                db.execute(
                    update(OutboxEvent)
                    .where(
                        OutboxEvent.id == event_id,
                        OutboxEvent.status == OUTBOX_PENDING,
                    )
                    .values(
                        publish_attempts=OutboxEvent.publish_attempts + 1,
                        last_error=f"{type(error).__name__}: {error}"[:MAX_ERROR_LENGTH],
                    )
                )
                db.commit()
        except Exception:
            logger.exception("Could not record publish failure for outbox event %s.", event_id)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("OutboxPublisher started (poll interval %ss).", self.poll_interval)
        while not stop_event.is_set():
            try:
                published = await asyncio.to_thread(self.publish_pending_once)
            except Exception:
                logger.exception("Outbox polling failed; retrying on the next cycle.")
                published = False
            if not published:
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.poll_interval,
                    )
                except asyncio.TimeoutError:
                    pass
        logger.info("OutboxPublisher stopped.")
