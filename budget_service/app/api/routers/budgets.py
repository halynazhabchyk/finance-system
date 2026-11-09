"""HTTP routes for budgets."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas import BudgetCreate, BudgetResponse, BudgetSummary, BudgetUpdate
from app.services import budgets as budget_service

router = APIRouter(prefix="/internal/budgets", tags=["budgets"])

BUDGET_PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


@router.get("", response_model=list[BudgetResponse])
def list_budgets(
    current_user: CurrentUser,
    db: DatabaseSession,
    period: Annotated[
        str | None,
        Query(
            pattern=BUDGET_PERIOD_PATTERN,
            description="Calendar month YYYY-MM. Returns at most one budget of that month.",
            examples=["2026-11"],
        ),
    ] = None,
):
    return budget_service.list_budgets(db, current_user, period=period)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(current_user: CurrentUser, payload: BudgetCreate, db: DatabaseSession):
    return budget_service.create_budget(db, current_user, payload)


@router.get("/{budget_id}", response_model=BudgetSummary)
def get_budget(budget_id: uuid.UUID, current_user: CurrentUser, db: DatabaseSession):
    return budget_service.get_budget_summary(db, budget_id, current_user)


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: BudgetUpdate,
    db: DatabaseSession,
):
    return budget_service.update_budget(db, budget_id, current_user, payload)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: uuid.UUID, current_user: CurrentUser, db: DatabaseSession):
    budget_service.delete_budget(db, budget_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
