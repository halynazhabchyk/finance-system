"""Compensating transaction CT1: cancel the expense of a failed saga."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.integrations.events import expense_payload, saga_fields
from app.models import Budget, Expense, SagaInstance
from app.models.expense import EXPENSE_CANCELLED
from app.models.saga_instance import SAGA_CANCELLED, SAGA_COMPLETED, STEP_EXPENSE_CANCELLED
from app.repositories import budgets as budget_repository
from app.repositories import sagas as saga_repository
from app.services.common import record_budget_change
from app.services.saga.lifecycle import SagaService, utcnow

logger = logging.getLogger(__name__)

FINISHED_STATUSES = (SAGA_CANCELLED, SAGA_COMPLETED)


def cancel_expense(
    db: Session,
    saga_id: uuid.UUID,
    reason: str,
    details: str,
    *,
    skip_locked: bool = False,
) -> bool:
    """CT1 in one local transaction. Idempotent: a finished saga is never cancelled twice.

    Returns True when this call cancelled the saga.
    """
    saga = _lock_unfinished_saga(db, saga_id, skip_locked=skip_locked)
    if saga is None:
        return False

    saga.compensation_attempts += 1
    if saga.failure_reason is None:
        saga.failure_reason = reason
        saga.failure_details = details

    expense, budget = _lock_expense_with_budget(db, saga.aggregate_id)
    if expense is None:
        # The budget (and its expenses) was deleted; BudgetDeleted already
        # cleaned up Report Service, so only the saga needs closing.
        saga.failure_details = f"{saga.failure_details} Expense no longer exists."
    elif budget is not None and expense.saga_status != EXPENSE_CANCELLED:
        _cancel_expense_record(db, saga, expense, budget)

    saga.status = SAGA_CANCELLED
    saga.current_step = STEP_EXPENSE_CANCELLED
    saga.finished_at = utcnow()
    saga.last_error = None
    db.commit()
    logger.warning(
        "Saga %s CANCELLED (reason %s): expense %s CANCELLED, ExpenseCancelled queued in outbox.",
        saga_id,
        saga.failure_reason,
        saga.aggregate_id,
    )
    return True


def _lock_unfinished_saga(
    db: Session,
    saga_id: uuid.UUID,
    *,
    skip_locked: bool,
) -> SagaInstance | None:
    saga = saga_repository.get_saga(db, saga_id, for_update=True, skip_locked=skip_locked)
    if saga is None:
        db.rollback()
        logger.info("Saga %s is unknown or locked by another worker; skipping.", saga_id)
        return None
    if saga.status in FINISHED_STATUSES:
        status = saga.status
        db.rollback()
        logger.info("Compensation for saga %s skipped: saga is already %s.", saga_id, status)
        return None
    return saga


def _lock_expense_with_budget(
    db: Session,
    expense_id: uuid.UUID,
) -> tuple[Expense | None, Budget | None]:
    """Lock the budget first, then the expense: the same order as the HTTP use cases."""
    expense = budget_repository.get_expense_by_id(db, expense_id)
    if expense is None:
        return None, None
    budget = budget_repository.get_budget(db, expense.budget_id, for_update=True)
    return budget_repository.get_expense_by_id(db, expense_id, for_update=True), budget


def _cancel_expense_record(db: Session, saga: SagaInstance, expense: Expense, budget: Budget) -> None:
    """Exclude the expense from totals and queue the newer snapshot for Report Service."""
    expense.saga_status = EXPENSE_CANCELLED
    record_budget_change(
        db,
        budget,
        "ExpenseCancelled",
        aggregate_type="Expense",
        aggregate_id=expense.expense_id,
        extra=saga_fields(
            saga,
            expense,
            cancellation_reason=saga.failure_reason,
            cancelled_expense=expense_payload(expense),
        ),
    )


class CompensationHandler:
    """Runs CT1 with its own sessions; failures are stored for a later retry."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        service: SagaService | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.service = service or SagaService()

    def compensate(
        self,
        saga_id: uuid.UUID,
        reason: str,
        details: str,
        *,
        skip_locked: bool = False,
    ) -> bool:
        """Mark COMPENSATING, run CT1; on failure keep the saga COMPENSATING and re-raise."""
        with self.session_factory() as db:
            if self.service.mark_compensating(db, saga_id, reason, details) is None:
                logger.warning("Compensation requested for unknown saga %s.", saga_id)
                return False
        try:
            return self._cancel(saga_id, reason, details, skip_locked=skip_locked)
        except Exception as error:
            logger.exception("Compensation of saga %s failed; it stays COMPENSATING.", saga_id)
            self._record_failure(saga_id, reason, details, error)
            raise

    def _cancel(self, saga_id: uuid.UUID, reason: str, details: str, *, skip_locked: bool) -> bool:
        with self.session_factory() as db:
            try:
                return cancel_expense(db, saga_id, reason, details, skip_locked=skip_locked)
            except Exception:
                db.rollback()
                raise

    def _record_failure(self, saga_id: uuid.UUID, reason: str, details: str, error: Exception) -> None:
        try:
            with self.session_factory() as db:
                self.service.record_compensation_failure(db, saga_id, reason, details, error)
        except Exception:
            logger.exception("Could not record compensation failure for saga %s.", saga_id)
