"""Asynchronous worker that publishes Budget Service outbox events."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories import outbox as repository
from shared.messaging.publisher import publish_event

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000


class OutboxPublisher:
    """Polling publisher: moves PENDING outbox rows to RabbitMQ in creation order."""

    def __init__(self, poll_interval: float | None = None, session_factory=None) -> None:
        self.poll_interval = poll_interval or get_settings().outbox_poll_interval
        self.session_factory = session_factory or SessionLocal

    def publish_pending_once(self) -> bool:
        """Publish the oldest available event, retaining the row lock until commit."""
        with self.session_factory() as db:
            event = repository.lock_next_pending(db)
            if event is None:
                db.rollback()
                return False
            event_id = event.id
            event_type = event.event_type
            try:
                publish_event(event.payload)
                repository.mark_published(event, datetime.now(timezone.utc))
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
                repository.record_failure(db, event_id, f"{type(error).__name__}: {error}"[:MAX_ERROR_LENGTH])
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
