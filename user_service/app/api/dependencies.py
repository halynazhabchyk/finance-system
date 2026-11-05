from collections.abc import Generator
import os

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.auth_service import get_user_id_from_token
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=os.getenv("PUBLIC_AUTH_URL", "/api/users/auth/login")
)


def get_db() -> Generator[Session, None, None]:
    """Provide one User Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_id(token: str = Depends(oauth2_scheme)):
    return get_user_id_from_token(token)
