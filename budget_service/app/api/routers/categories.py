"""HTTP routes for categories of a budget."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession
from app.schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import categories as category_service

router = APIRouter(prefix="/internal/budgets/{budget_id}/categories", tags=["categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    budget_id: uuid.UUID,
    current_user: CurrentUser,
    payload: CategoryCreate,
    db: DatabaseSession,
):
    return category_service.create_category(db, budget_id, current_user, payload)


@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: CurrentUser,
    payload: CategoryUpdate,
    db: DatabaseSession,
):
    return category_service.update_category(db, budget_id, category_id, current_user, payload)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    budget_id: uuid.UUID,
    category_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    category_service.delete_category(db, budget_id, category_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
