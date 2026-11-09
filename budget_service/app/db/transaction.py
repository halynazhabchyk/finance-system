"""One local transaction per use case, with database errors mapped to domain errors."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from shared.errors import (
    BusinessRuleError,
    ConflictError,
    DomainError,
    ServiceUnavailableError,
)

DATABASE_UNAVAILABLE = "The budget database is temporarily unavailable."

# Constraint name -> client message for unique violations (HTTP 409).
UNIQUE_CONSTRAINT_MESSAGES = {
    "uq_budgets_user_period": "A budget already exists for this user and calendar month.",
    "uq_categories_budget_name": "A category with this name already exists in this budget.",
}


@contextmanager
def write_transaction(db: Session) -> Iterator[None]:
    """Run the block and COMMIT it; on any failure roll everything back.

    The business change and its outbox row are written in the same block,
    so they are committed or discarded together (Transactional Outbox).
    """
    try:
        yield
        commit(db)
    except DomainError:
        db.rollback()
        raise
    except IntegrityError as error:
        # Raised by an explicit flush() inside the block, before commit().
        db.rollback()
        raise _integrity_error(error) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise ServiceUnavailableError(DATABASE_UNAVAILABLE) from error


def commit(db: Session) -> None:
    """Flush and commit, translating constraint violations into domain errors."""
    try:
        db.flush()
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _integrity_error(error) from error
    except OperationalError as error:
        db.rollback()
        raise ServiceUnavailableError("The database is temporarily unavailable.") from error
    except SQLAlchemyError as error:
        db.rollback()
        raise ServiceUnavailableError("The database operation could not be completed.") from error


def _integrity_error(error: IntegrityError) -> DomainError:
    constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", "") or ""
    if constraint.startswith("uq_"):
        return ConflictError(
            UNIQUE_CONSTRAINT_MESSAGES.get(constraint, "The resource conflicts with existing data.")
        )
    if constraint.startswith("ck_"):
        return BusinessRuleError("The submitted values violate a data rule.")
    if constraint.startswith(("fk_", "expenses_")):
        return BusinessRuleError("The submitted resource relationship is invalid.")
    return BusinessRuleError("The submitted data conflicts with a database rule.")
