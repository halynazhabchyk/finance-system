"""Business logic for UserAccount management."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import UserAccount
from app.repositories import users as user_repository
from app.schemas import UserCreate, UserUpdateName


def get_user_or_404(db: Session, user_id: uuid.UUID) -> UserAccount:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User was not found.",
        )
    return user


def list_users(db: Session, limit: int, offset: int) -> list[UserAccount]:
    return user_repository.get_all(db, limit=limit, offset=offset)


def create_user(db: Session, payload: UserCreate) -> UserAccount:
    email = str(payload.email).strip().lower()
    if user_repository.get_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    try:
        user = user_repository.create(
            db,
            user_name=payload.user_name,
            email=email,
            password_hash=hash_password(payload.password),
        )
        _commit_or_raise_conflict(db)
    except ValueError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password cannot be processed.",
        ) from error

    db.refresh(user)
    return user


def update_user_name(
    db: Session,
    user_id: uuid.UUID,
    payload: UserUpdateName,
) -> UserAccount:
    user = get_user_or_404(db, user_id)
    user_repository.update_name(db, user, payload.user_name)
    _commit_or_raise_conflict(db)
    db.refresh(user)
    return user


def activate_user(db: Session, user_id: uuid.UUID) -> UserAccount:
    return _set_user_status(db, user_id, is_active=True)


def block_user(db: Session, user_id: uuid.UUID) -> UserAccount:
    return _set_user_status(db, user_id, is_active=False)


def _set_user_status(
    db: Session,
    user_id: uuid.UUID,
    *,
    is_active: bool,
) -> UserAccount:
    user = get_user_or_404(db, user_id)
    user_repository.update_status(db, user, is_active)
    _commit_or_raise_conflict(db)
    db.refresh(user)
    return user


def _commit_or_raise_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The user conflicts with existing data.",
        ) from error
