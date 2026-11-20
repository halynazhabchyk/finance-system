"""Data access for outbox rows (no business rules here)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import OutboxEvent
from app.models.outbox_event import OUTBOX_PENDING, OUTBOX_PUBLISHED


def lock_next_pending(db: Session) -> OutboxEvent | None:
    """Oldest PENDING row, locked until commit; rows locked by other instances are skipped."""
    return db.scalar(
        select(OutboxEvent)
        .where(OutboxEvent.status == OUTBOX_PENDING)
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def mark_published(event: OutboxEvent, published_at: datetime) -> None:
    event.status = OUTBOX_PUBLISHED
    event.published_at = published_at
    event.publish_attempts += 1
    event.last_error = None


def record_failure(db: Session, event_id: uuid.UUID, last_error: str) -> None:
    """Count the attempt and keep the error; the row stays PENDING."""
    db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.id == event_id, OutboxEvent.status == OUTBOX_PENDING)
        .values(publish_attempts=OutboxEvent.publish_attempts + 1, last_error=last_error)
    )
