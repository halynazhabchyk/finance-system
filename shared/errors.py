"""Domain errors raised by the service layer of every microservice.

Services describe *what* went wrong and do not depend on FastAPI;
``shared.web.errors`` decides which HTTP status each error becomes.
"""


class DomainError(Exception):
    """Base class for expected failures with a client-safe message."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    """The resource does not exist or belongs to another user."""


class ConflictError(DomainError):
    """The request conflicts with the current state of the resource."""


class BusinessRuleError(DomainError):
    """The request violates a domain invariant."""


class AuthenticationError(DomainError):
    """Credentials or token are missing, invalid or expired."""


class PermissionDeniedError(DomainError):
    """The caller is known but is not allowed to perform the operation."""


class ServiceUnavailableError(DomainError):
    """A dependency (database, another service) is temporarily unavailable."""
