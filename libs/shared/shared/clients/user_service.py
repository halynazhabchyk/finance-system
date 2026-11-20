"""Client of the User Service Open Host Service GET /internal/users/{user_id}.

Raises shared domain errors; the API layer of the caller turns them into HTTP responses.
"""

from __future__ import annotations

import logging
import os
import uuid

import httpx

from shared.errors import AuthenticationError, ConflictError, PermissionDeniedError, ServiceUnavailableError
from shared.service_discovery.consul import (
    ConsulError,
    discover_service,
)

logger = logging.getLogger(__name__)

UNAVAILABLE = "User Service is temporarily unavailable."


def validate_user_token(token: str, user_id: uuid.UUID) -> dict:
    service_name = os.getenv("USER_SERVICE_NAME", "user-service")
    timeout = float(os.getenv("USER_SERVICE_REQUEST_TIMEOUT", "5"))
    try:
        base_url = discover_service(service_name, request_timeout=timeout)
        response = httpx.get(
            f"{base_url.rstrip('/')}/internal/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
        )
    except (ConsulError, httpx.RequestError) as error:
        logger.warning("user_service_unavailable error=%s", type(error).__name__)
        raise ServiceUnavailableError(UNAVAILABLE) from error

    if response.status_code == 200:
        return response.json()
    logger.warning("user_service_rejected status=%s sub=%s", response.status_code, user_id)
    if response.status_code == 403:
        raise PermissionDeniedError("The user account is not allowed to use the service.")
    if response.status_code == 409:
        raise ConflictError("The account cannot be linked to a user profile.")
    if response.status_code >= 500:
        raise ServiceUnavailableError(UNAVAILABLE)
    # 401, 404, 422 and anything unexpected: the caller has to sign in again.
    raise AuthenticationError("Invalid or missing access token.")
