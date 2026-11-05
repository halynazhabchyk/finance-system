import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user_id, get_db
from app.schemas import UserCreate, UserResponse, UserUpdateName
from app.services import user_service


router = APIRouter(prefix="/internal/users", tags=["users"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[UserResponse])
def list_users(
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    return user_service.list_users(db, limit=limit, offset=offset)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DatabaseSession) -> UserResponse:
    return user_service.create_user(db, payload)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: uuid.UUID,
    db: DatabaseSession,
    current_user_id: uuid.UUID = Depends(get_current_user_id),
) -> UserResponse:
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The token does not authorize access to this user.",
        )
    return user_service.get_user_or_404(db, user_id)


@router.patch("/{user_id}/name", response_model=UserResponse)
def update_user_name(
    user_id: uuid.UUID,
    payload: UserUpdateName,
    db: DatabaseSession,
) -> UserResponse:
    return user_service.update_user_name(db, user_id, payload)


@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(user_id: uuid.UUID, db: DatabaseSession) -> UserResponse:
    return user_service.activate_user(db, user_id)


@router.patch("/{user_id}/block", response_model=UserResponse)
def block_user(user_id: uuid.UUID, db: DatabaseSession) -> UserResponse:
    return user_service.block_user(db, user_id)
