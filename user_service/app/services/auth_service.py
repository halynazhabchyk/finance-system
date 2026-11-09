"""Authentication use cases: login and access-token validation."""

import uuid

from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from shared.errors import AuthenticationError, PermissionDeniedError

from app.core.security import create_access_token, decode_access_token, verify_password
from app.repositories import users as user_repository
from app.schemas.auth import TokenResponse


def authenticate_user(db: Session, *, email: str, password: str) -> TokenResponse:
    user = user_repository.get_by_email(db, email.strip().lower())
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise PermissionDeniedError("The user account is inactive.")
    return TokenResponse(access_token=create_access_token(str(user.user_id)))


def get_user_id_from_token(token: str) -> uuid.UUID:
    try:
        return uuid.UUID(decode_access_token(token).get("sub"))
    except (InvalidTokenError, TypeError, ValueError, RuntimeError) as error:
        raise AuthenticationError("Invalid or expired access token.") from error
