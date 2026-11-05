from collections.abc import Generator
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from shared.clients.user_service import validate_user_token


SERVICE_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(SERVICE_ROOT / ".env")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=os.getenv("PUBLIC_AUTH_URL", "/api/users/auth/login")
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    """Validate the token and subject through the User Service."""
    try:
        subject = jwt.decode(
            token,
            os.getenv("JWT_SECRET_KEY", ""),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")],
            options={"verify_signature": False},
        ).get("sub")
    except (jwt.InvalidTokenError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    try:
        user_id = uuid.UUID(subject)
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    validate_user_token(token, user_id)
    return user_id


def get_db() -> Generator[Session, None, None]:
    """Yield one Budget Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
