"""FastAPI dependencies: database session and the authenticated user."""

from collections.abc import Generator
from typing import Annotated
import uuid

from fastapi import Depends, Security
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from shared.clients.user_service import validate_user_token
from shared.security.fastapi import bearer_token_dependency
from shared.security.jwt import VerifiedToken
from shared.security.openapi import authorization_code_scheme


# Scopes shown in the Swagger Authorize dialog.
SERVICE_SCOPES = ["budgets:read", "budgets:write"]
oauth2_scheme = authorization_code_scheme(SERVICE_SCOPES, auto_error=False)
verified_token = bearer_token_dependency(oauth2_scheme)


def get_current_user(token: Annotated[VerifiedToken, Security(verified_token)]) -> uuid.UUID:
    """user_id = sub of the verified token; User Service rejects blocked accounts."""
    validate_user_token(token.raw, token.user_id)
    return token.user_id


def get_db() -> Generator[Session, None, None]:
    """Yield one Budget Service database session per HTTP request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Shortcuts for route signatures.
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
# Scope is checked before User Service is called.
BudgetReader = Annotated[uuid.UUID, Security(get_current_user, scopes=["budgets:read"])]
BudgetWriter = Annotated[uuid.UUID, Security(get_current_user, scopes=["budgets:write"])]
