"""Shared Budget Service business helpers."""

import calendar
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import budgets as repository

def commit(db: Session) -> None:
    try:
        db.flush()
        db.commit()
    except IntegrityError as error:
        db.rollback()
        constraint_name = getattr(getattr(error.orig, "diag", None), "constraint_name", "")
        if constraint_name == "uq_budgets_user_period":
            detail = "A budget already exists for this user and calendar month."
        elif constraint_name == "uq_categories_budget_name":
            detail = "A category with this name already exists in this budget."
        elif constraint_name and constraint_name.startswith("uq_"):
            detail = "The resource conflicts with existing data."
        elif constraint_name and constraint_name.startswith("ck_"):
            detail = "The submitted values violate a data rule."
        elif constraint_name and constraint_name.startswith(("fk_", "expenses_")):
            detail = "The submitted resource relationship is invalid."
        else:
            detail = "The submitted data conflicts with a database rule."
        status_code = 409 if constraint_name and constraint_name.startswith("uq_") else 422
        raise HTTPException(status_code=status_code, detail=detail) from error
    except OperationalError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The database is temporarily unavailable.",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="The database operation could not be completed.",
        ) from error


def budget_or_404(
    db: Session,
    budget_id: uuid.UUID,
    user_id: uuid.UUID,
):
    budget = repository.get_budget(db, budget_id)
    if budget is None or budget.user_id != user_id:
        raise HTTPException(status_code=404, detail="Budget was not found.")
    return budget


def validate_period(period_start, period_end) -> None:
    last_day = calendar.monthrange(period_start.year, period_start.month)[1]
    if (
        period_start.day != 1
        or period_end.year != period_start.year
        or period_end.month != period_start.month
        or period_end.day != last_day
    ):
        raise HTTPException(
            status_code=422,
            detail="A budget period must cover one complete calendar month.",
        )
