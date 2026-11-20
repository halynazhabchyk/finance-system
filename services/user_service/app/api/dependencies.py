"""FastAPI dependencies: database session and the profile of the token subject."""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Security
from sqlalchemy.orm import Session

from shared.errors import PermissionDeniedError
from shared.security.fastapi import bearer_token_dependency
from shared.security.jwt import VerifiedToken
from shared.security.openapi import authorization_code_scheme

from app.db.session import SessionLocal
from app.models import UserAccount
from app.services import user_service
from app.services.provisioning import ProfileClaims


# Scopes shown in the Swagger Authorize dialog.
SERVICE_SCOPES = ["users:read", "users:write"]
oauth2_scheme = authorization_code_scheme(SERVICE_SCOPES, auto_error=False)
verified_token = bearer_token_dependency(oauth2_scheme)


def get_db() -> Generator[Session, None, None]:
    """Provide one User Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_profile(
    token: Annotated[VerifiedToken, Security(verified_token)],
    db: DatabaseSession,
) -> UserAccount:
    """Profile of the token subject, created at the first sign-in; blocked profile -> 403."""
    profile = user_service.get_or_create_profile(db, ProfileClaims.from_token(token.claims))
    if not profile.is_active:
        raise PermissionDeniedError("The user account is blocked.")
    return profile


CurrentProfile = Annotated[UserAccount, Depends(get_current_profile)]
# Reading and renaming need different scopes.
ProfileReader = Annotated[UserAccount, Security(get_current_profile, scopes=["users:read"])]
ProfileWriter = Annotated[UserAccount, Security(get_current_profile, scopes=["users:write"])]
