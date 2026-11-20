"""HTTP mapping of shared domain errors (``shared.errors``)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.errors import (
    AuthenticationError,
    BusinessRuleError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
)

STATUS_BY_ERROR: dict[type[DomainError], int] = {
    AuthenticationError: 401,
    PermissionDeniedError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    BusinessRuleError: 422,
    ServiceUnavailableError: 503,
}
DEFAULT_STATUS = 400


def status_for(error: DomainError) -> int:
    """Status of the closest mapped base class, so subclasses inherit it."""
    for error_type in type(error).__mro__:
        if error_type in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[error_type]
    return DEFAULT_STATUS


async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(error, AuthenticationError) else None
    return JSONResponse(
        status_code=status_for(error),
        content={"detail": error.detail},
        headers=headers,
    )


def register_domain_error_handler(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, handle_domain_error)
