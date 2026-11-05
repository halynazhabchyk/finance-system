"""Budget Service HTTP routes."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas import (
    BudgetCreate,
    BudgetResponse,
    BudgetSummary,
    BudgetUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
)
from app.services import budgets, categories, expenses


router = APIRouter(prefix="/internal/budgets", tags=["budgets"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]


@router.get("", response_model=list[BudgetResponse])
def list_budgets(current_user: CurrentUser, db: DatabaseSession):
    return budgets.list_budgets(db, current_user)


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    current_user: CurrentUser,
    payload: BudgetCreate,
    db: DatabaseSession,
):
    return budgets.create_budget(db, current_user, payload)


@router.get("/{budget_id}", response_model=BudgetSummary)
def get_budget(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    return budgets.get_budget_summary(db, budget_id, current_user)


@router.get("/{budget_id}/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    return expenses.list_expenses(db, budget_id, current_user)


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: BudgetUpdate,
    db: DatabaseSession,
):
    return budgets.update_budget(db, budget_id, current_user, payload)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    budgets.delete_budget(db, budget_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{budget_id}/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: CategoryCreate,
    db: DatabaseSession,
):
    return categories.create_category(db, budget_id, current_user, payload)


@router.patch(
    "/{budget_id}/categories/{category_id}",
    response_model=CategoryResponse,
)
def update_category(
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: CurrentUser,
    payload: CategoryUpdate,
    db: DatabaseSession,
):
    return categories.update_category(
        db,
        budget_id,
        category_id,
        current_user,
        payload,
    )


@router.delete(
    "/{budget_id}/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_category(
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    categories.delete_category(db, budget_id, category_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{budget_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: ExpenseCreate,
    db: DatabaseSession,
):
    return expenses.create_expense(db, budget_id, current_user, payload)


@router.patch(
    "/{budget_id}/expenses/{expense_id}",
    response_model=ExpenseResponse,
)
def update_expense(
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    payload: ExpenseUpdate,
    db: DatabaseSession,
):
    return expenses.update_expense(
        db,
        budget_id,
        expense_id,
        current_user,
        payload,
    )


@router.delete(
    "/{budget_id}/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_expense(
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    expenses.delete_expense(db, budget_id, expense_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
