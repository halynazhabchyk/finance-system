"""Authentication business logic."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.repositories import users as user_repository
from app.schemas.auth import TokenResponse


def authenticate_user(db: Session, *, email: str, password: str) -> TokenResponse:
    email = email.strip().lower()
    user = user_repository.get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user account is inactive.",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.user_id)),
    )


def get_user_id_from_token(token: str) -> uuid.UUID:
    from jwt import InvalidTokenError

    from app.core.security import decode_access_token

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        return uuid.UUID(subject)
    except (InvalidTokenError, TypeError, ValueError, RuntimeError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
