"""RabbitMQ worker that updates the Report Service read model."""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from shared.messaging.rabbitmq import EventConsumer, PermanentEventError

from app.db.session import SessionLocal
from app.repositories import reports as repository

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False


class ReportEventConsumer:
    """Consume Budget and Scheduler events with transactional acknowledgements."""

    def __init__(self) -> None:
        self._consumer = EventConsumer(
            queue_name="report-service-events",
            routing_keys=[
                "BudgetCreated",
                "BudgetUpdated",
                "ExpenseCreated",
                "ExpenseUpdated",
                "ExpenseDeleted",
                "BudgetDeleted",
                "DailyReportUpdateRequested",
                "MonthlyReportUpdateRequested",
            ],
            handler=self.handle,
        )

    def start(self) -> None:
        self._consumer.start()

    def stop(self) -> None:
        self._consumer.stop()

    def handle(self, event: dict) -> None:
        if event.get("event_version") != 1:
            raise PermanentEventError(
                f"Unsupported event version: {event.get('event_version')}"
            )
        db = SessionLocal()
        try:
            event_id = uuid.UUID(event["event_id"])
            if repository.event_processed(db, event_id):
                logger.info("Skipping duplicate event %s.", event_id)
                return

            event_type = event["event_type"]
            if event_type == "BudgetDeleted":
                repository.apply_budget_deleted(db, event)
            elif event_type in {
                "BudgetCreated",
                "BudgetUpdated",
                "ExpenseCreated",
                "ExpenseUpdated",
                "ExpenseDeleted",
            }:
                repository.apply_budget_snapshot(db, event)
            elif event_type in {
                "DailyReportUpdateRequested",
                "MonthlyReportUpdateRequested",
            }:
                repository.refresh_reports(
                    db,
                    datetime.fromisoformat(event["created_at"]).astimezone(
                        timezone.utc
                    ),
                )

            repository.mark_event_processed(db, event_id)
            db.commit()
            logger.info("Processed event %s (%s).", event_id, event_type)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
