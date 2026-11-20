import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import DatabaseSession, ProfileReader, ProfileWriter
from app.schemas import UserResponse, UserUpdateName
from app.services import user_service


router = APIRouter(prefix="/internal/users", tags=["users"])


# Internal: not published through Traefik.
@router.get("", response_model=list[UserResponse])
def list_users(
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[UserResponse]:
    return user_service.list_users(db, limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, profile: ProfileReader) -> UserResponse:
    """Open Host Service: own profile of the token subject (created at the first sign-in)."""
    user_service.require_owner(profile, user_id)
    return profile


@router.patch("/{user_id}/name", response_model=UserResponse)
def update_user_name(
    user_id: uuid.UUID,
    payload: UserUpdateName,
    db: DatabaseSession,
    profile: ProfileWriter,
) -> UserResponse:
    return user_service.rename_own_profile(db, profile, user_id, payload)


# Internal: not published through Traefik.
@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(user_id: uuid.UUID, db: DatabaseSession) -> UserResponse:
    return user_service.activate_user(db, user_id)


@router.patch("/{user_id}/block", response_model=UserResponse)
def block_user(user_id: uuid.UUID, db: DatabaseSession) -> UserResponse:
    return user_service.block_user(db, user_id)
