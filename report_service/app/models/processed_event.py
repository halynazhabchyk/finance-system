"""Transactional Inbox record for events consumed by Report Service.

A row is inserted in the same local transaction as the read-model change, so
it exists only for events whose business operation was committed.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PROCESSED')",
            name="ck_processed_events_status",
        ),
    )

    # Primary key guarantees message-id uniqueness (requirement 4.9).
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PROCESSED",
        server_default="PROCESSED",
    )

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
