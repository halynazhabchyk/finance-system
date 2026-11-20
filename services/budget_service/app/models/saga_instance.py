"""State of one distributed operation (SAGA) coordinated by Budget Service."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


SAGA_STARTED = "STARTED"
SAGA_COMPLETED = "COMPLETED"
SAGA_COMPENSATING = "COMPENSATING"
SAGA_CANCELLED = "CANCELLED"

SAGA_TYPE_CREATE_EXPENSE = "CreateExpense"

# Values of current_step: the last step the saga has reached.
STEP_EXPENSE_CREATED = "EXPENSE_CREATED"
STEP_REPORT_CONFIRMED = "REPORT_CONFIRMED"
STEP_COMPENSATION_REQUESTED = "COMPENSATION_REQUESTED"
STEP_EXPENSE_CANCELLED = "EXPENSE_CANCELLED"

REASON_DLQ = "DLQ"
REASON_TIMEOUT = "TIMEOUT"


class SagaInstance(Base):
    __tablename__ = "saga_instances"
    __table_args__ = (
        UniqueConstraint(
            "saga_type",
            "aggregate_id",
            name="uq_saga_instances_type_aggregate",
        ),
        CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'COMPENSATING', 'CANCELLED')",
            name="ck_saga_instances_status",
        ),
        CheckConstraint(
            "failure_reason IS NULL OR failure_reason IN ('DLQ', 'TIMEOUT')",
            name="ck_saga_instances_failure_reason",
        ),
        Index("ix_saga_instances_status_deadline", "status", "deadline_at"),
    )

    saga_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    saga_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_step: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    compensation_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
