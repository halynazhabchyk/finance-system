"""HTTP routes for expenses of a budget and the state of their SAGA."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate, SagaResponse
from app.services import expenses as expense_service

router = APIRouter(prefix="/internal/budgets/{budget_id}/expenses", tags=["expenses"])


@router.get("", response_model=list[ExpenseResponse])
def list_expenses(budget_id: uuid.UUID, current_user: CurrentUser, db: DatabaseSession):
    return expense_service.list_expenses(db, budget_id, current_user)


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: ExpenseCreate,
    db: DatabaseSession,
):
    return expense_service.create_expense(db, budget_id, current_user, payload)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    payload: ExpenseUpdate,
    db: DatabaseSession,
):
    return expense_service.update_expense(db, budget_id, expense_id, current_user, payload)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    expense_service.delete_expense(db, budget_id, expense_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{expense_id}/saga", response_model=SagaResponse)
def get_expense_saga(
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    return expense_service.get_expense_saga(db, budget_id, expense_id, current_user)
