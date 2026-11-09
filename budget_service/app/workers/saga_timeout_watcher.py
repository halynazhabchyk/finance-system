"""Background watcher that cancels sagas without a reply before their deadline."""

from __future__ import annotations

import asyncio
import logging
import os

from app.db.session import SessionLocal
from app.models.saga_instance import REASON_TIMEOUT
from app.repositories import sagas as saga_repository
from app.services.saga import CompensationHandler, utcnow

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


class SagaTimeoutWatcher:
    def __init__(
        self,
        interval: float | None = None,
        session_factory=None,
        handler: CompensationHandler | None = None,
    ) -> None:
        self.interval = interval or float(os.getenv("SAGA_WATCH_INTERVAL", "5"))
        self.session_factory = session_factory or SessionLocal
        self.handler = handler or CompensationHandler(self.session_factory)

    def check_once(self) -> int:
        """Compensate overdue STARTED sagas and retry unfinished compensations."""
        with self.session_factory() as db:
            saga_ids = saga_repository.find_sagas_needing_compensation(
                db,
                utcnow(),
                BATCH_SIZE,
            )
            db.rollback()
        cancelled = 0
        for saga_id in saga_ids:
            logger.warning("SagaTimeoutWatcher: saga %s is overdue or unfinished.", saga_id)
            try:
                if self.handler.compensate(
                    saga_id,
                    REASON_TIMEOUT,
                    "No ExpenseProcessed was received before the saga deadline.",
                    skip_locked=True,
                ):
                    cancelled += 1
            except Exception:
                # Already recorded as COMPENSATING; the next cycle retries it.
                logger.exception("SagaTimeoutWatcher could not compensate saga %s.", saga_id)
        return cancelled

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("SagaTimeoutWatcher started (interval %ss).", self.interval)
        while not stop_event.is_set():
            try:
                await asyncio.to_thread(self.check_once)
            except Exception:
                logger.exception("SagaTimeoutWatcher cycle failed; retrying later.")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
        logger.info("SagaTimeoutWatcher stopped.")
