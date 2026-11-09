"""FastAPI dependencies: database session and the authenticated user."""

import os
import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from shared.clients.user_service import validate_user_token

from app.db.session import SessionLocal

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=os.getenv("PUBLIC_AUTH_URL", "/api/users/auth/login")
)


def get_db() -> Generator[Session, None, None]:
    """Yield one Report Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    """Read the subject from the token; User Service confirms the token and the account."""
    try:
        subject = jwt.decode(token, options={"verify_signature": False}).get("sub")
        user_id = uuid.UUID(subject)
    except (jwt.InvalidTokenError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    validate_user_token(token, user_id)
    return user_id


# Shortcuts for route signatures.
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
