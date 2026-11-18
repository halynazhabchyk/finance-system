"""FastAPI dependencies: database session and the authenticated user (ЛР №5: Keycloak token)."""

import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Security
from sqlalchemy.orm import Session

from shared.clients.user_service import validate_user_token
from shared.security.fastapi import bearer_token_dependency
from shared.security.jwt import VerifiedToken
from shared.security.openapi import authorization_code_scheme

from app.db.session import SessionLocal

# OAuth scopes of this service's resources, shown in the Swagger "Authorize" dialog.
SERVICE_SCOPES = ["reports:read"]
oauth2_scheme = authorization_code_scheme(SERVICE_SCOPES, auto_error=False)
verified_token = bearer_token_dependency(oauth2_scheme)


def get_db() -> Generator[Session, None, None]:
    """Yield one Report Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(token: Annotated[VerifiedToken, Security(verified_token)]) -> uuid.UUID:
    """``user_id`` = ``sub`` of the token this service verified itself; User Service confirms the account."""
    validate_user_token(token.raw, token.user_id)
    return token.user_id


# Shortcuts for route signatures.
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
# ЛР №5, п. 4: the scope is checked locally before User Service is asked (403 insufficient_scope).
ReportReader = Annotated[uuid.UUID, Security(get_current_user, scopes=["reports:read"])]
