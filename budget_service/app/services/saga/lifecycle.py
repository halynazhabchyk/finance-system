"""SAGA state transitions: start, confirm, start and record compensation."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.models import SagaInstance
from app.models.expense import EXPENSE_CONFIRMED, EXPENSE_PENDING
from app.models.saga_instance import (
    SAGA_COMPENSATING,
    SAGA_COMPLETED,
    SAGA_STARTED,
    SAGA_TYPE_CREATE_EXPENSE,
    STEP_COMPENSATION_REQUESTED,
    STEP_EXPENSE_CREATED,
    STEP_REPORT_CONFIRMED,
)
from app.repositories import budgets as budget_repository
from app.repositories import sagas as saga_repository

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000


def saga_timeout_seconds() -> int:
    return max(1, int(os.getenv("SAGA_TIMEOUT_SECONDS", "30")))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SagaService:
    """Keeps saga state. Methods named after a local transaction commit it."""

    def start_create_expense(self, db: Session, expense_id: uuid.UUID) -> SagaInstance:
        """Persist the initial saga state inside T1 (requirement 5.6). No commit."""
        now = utcnow()
        saga = SagaInstance(
            saga_id=uuid.uuid4(),
            saga_type=SAGA_TYPE_CREATE_EXPENSE,
            aggregate_type="Expense",
            aggregate_id=expense_id,
            status=SAGA_STARTED,
            current_step=STEP_EXPENSE_CREATED,
            started_at=now,
            deadline_at=now + timedelta(seconds=saga_timeout_seconds()),
            compensation_attempts=0,
        )
        saga_repository.add_saga(db, saga)
        return saga

    def get_for_expense(self, db: Session, expense_id: uuid.UUID) -> SagaInstance | None:
        return saga_repository.get_saga_for_aggregate(db, SAGA_TYPE_CREATE_EXPENSE, expense_id)

    def confirm(self, db: Session, saga_id: uuid.UUID) -> bool:
        """Finish the saga after ExpenseProcessed. Idempotent; late replies are ignored (8.7)."""
        saga = saga_repository.get_saga(db, saga_id, for_update=True)
        if saga is None:
            db.rollback()
            logger.warning("ExpenseProcessed for unknown saga %s ignored.", saga_id)
            return False
        if saga.status != SAGA_STARTED:
            db.rollback()
            logger.info(
                "Late ExpenseProcessed for saga %s ignored: saga is already %s.",
                saga_id,
                saga.status,
            )
            return False

        expense = budget_repository.get_expense_by_id(db, saga.aggregate_id, for_update=True)
        if expense is not None and expense.saga_status == EXPENSE_PENDING:
            expense.saga_status = EXPENSE_CONFIRMED
        saga.status = SAGA_COMPLETED
        saga.current_step = STEP_REPORT_CONFIRMED
        saga.finished_at = utcnow()
        db.commit()
        logger.info("Saga %s COMPLETED: expense %s CONFIRMED.", saga_id, saga.aggregate_id)
        return True

    def mark_compensating(
        self,
        db: Session,
        saga_id: uuid.UUID,
        reason: str,
        details: str,
    ) -> str | None:
        """Record the decision to compensate before doing it (5.13). Returns the saga status."""
        saga = saga_repository.get_saga(db, saga_id, for_update=True)
        if saga is None:
            db.rollback()
            return None
        if saga.status != SAGA_STARTED:
            status = saga.status
            db.rollback()
            return status

        saga.status = SAGA_COMPENSATING
        saga.current_step = STEP_COMPENSATION_REQUESTED
        saga.failure_reason = reason
        saga.failure_details = details
        db.commit()
        logger.warning("Saga %s COMPENSATING (reason %s): %s", saga_id, reason, details)
        return SAGA_COMPENSATING

    def record_compensation_failure(
        self,
        db: Session,
        saga_id: uuid.UUID,
        reason: str,
        details: str,
        error: Exception,
    ) -> None:
        """Keep an unfinished compensation visible and retryable (6.8)."""
        db.execute(
            update(SagaInstance)
            .where(
                SagaInstance.saga_id == saga_id,
                SagaInstance.status.in_((SAGA_STARTED, SAGA_COMPENSATING)),
            )
            .values(
                status=SAGA_COMPENSATING,
                current_step=STEP_COMPENSATION_REQUESTED,
                # Keep the first reason (e.g. DLQ) when a retry comes from the watcher.
                failure_reason=func.coalesce(SagaInstance.failure_reason, reason),
                failure_details=func.coalesce(SagaInstance.failure_details, details),
                compensation_attempts=SagaInstance.compensation_attempts + 1,
                last_error=f"{type(error).__name__}: {error}"[:MAX_ERROR_LENGTH],
            )
        )
        db.commit()


saga_service = SagaService()
