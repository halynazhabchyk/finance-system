"""Repository for UserAccount database operations."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserAccount


def get_by_id(db: Session, user_id: uuid.UUID) -> UserAccount | None:
    """Get a user by UUID."""
    statement = select(UserAccount).where(
        UserAccount.user_id == user_id
    )
    return db.scalar(statement)


def get_by_email(db: Session, email: str) -> UserAccount | None:
    """Get a user by normalized email."""
    normalized_email = email.strip().lower()

    statement = select(UserAccount).where(
        UserAccount.email == normalized_email
    )
    return db.scalar(statement)


def get_all(
    db: Session,
    limit: int = 100,
    offset: int = 0,
) -> list[UserAccount]:
    """Get users with pagination."""
    statement = (
        select(UserAccount)
        .order_by(UserAccount.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


def create(
    db: Session,
    user_name: str,
    email: str,
    password_hash: str,
) -> UserAccount:
    """Create a new user."""
    user = UserAccount(
        user_name=user_name.strip(),
        email=email.strip().lower(),
        password_hash=password_hash,
    )

    db.add(user)
    db.flush()

    return user


def update_name(
    db: Session,
    user: UserAccount,
    user_name: str,
) -> UserAccount:
    """Update user's name."""
    user.user_name = user_name.strip()
    db.flush()

    return user


def update_status(
    db: Session,
    user: UserAccount,
    is_active: bool,
) -> UserAccount:
    """Update user's active status."""
    user.is_active = is_active
    db.flush()

    return user