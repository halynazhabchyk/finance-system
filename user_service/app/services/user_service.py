"""Use cases for UserAccount management."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shared.errors import ConflictError, NotFoundError

from app.models import UserAccount
from app.repositories import users as user_repository
from app.schemas import UserUpdateName
from app.services.provisioning import ProfileClaims


def get_user_or_404(db: Session, user_id: uuid.UUID) -> UserAccount:
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User was not found.")
    return user


def list_users(db: Session, limit: int, offset: int) -> list[UserAccount]:
    return user_repository.get_all(db, limit=limit, offset=offset)


def get_or_create_profile(db: Session, claims: ProfileClaims) -> UserAccount:
    """Return the profile of the token subject, creating it at the first sign-in (JIT provisioning).

    ``user_id`` is the Keycloak ``sub``; the profile is filled from the token
    claims, never from the Keycloak database.
    """
    user = user_repository.get_by_id(db, claims.user_id)
    if user is not None:
        return user
    if user_repository.get_by_email(db, claims.email) is not None:
        # An older local profile owns this email; merging accounts automatically is not safe.
        raise ConflictError("A profile with this email already exists under another identity.")
    user = user_repository.create(db, user_id=claims.user_id, user_name=claims.user_name, email=claims.email)
    try:
        db.commit()
    except IntegrityError:
        # Two first requests of the same user raced: the other one created the profile.
        db.rollback()
        user = user_repository.get_by_id(db, claims.user_id)
        if user is None:
            raise ConflictError("The profile conflicts with existing data.")
        return user
    db.refresh(user)
    return user


def update_user_name(db: Session, user_id: uuid.UUID, payload: UserUpdateName) -> UserAccount:
    user = get_user_or_404(db, user_id)
    user_repository.update_name(db, user, payload.user_name)
    _commit_or_raise_conflict(db)
    db.refresh(user)
    return user


def activate_user(db: Session, user_id: uuid.UUID) -> UserAccount:
    return _set_user_status(db, user_id, is_active=True)


def block_user(db: Session, user_id: uuid.UUID) -> UserAccount:
    return _set_user_status(db, user_id, is_active=False)


def _set_user_status(db: Session, user_id: uuid.UUID, *, is_active: bool) -> UserAccount:
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
        raise ConflictError("The user conflicts with existing data.") from error
