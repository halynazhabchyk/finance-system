"""Synchronous client for the User Service Open Host Service."""

from __future__ import annotations

import os
import uuid

import httpx
from fastapi import HTTPException, status

from shared.service_discovery.consul import (
    ConsulError,
    discover_service,
)


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
    except (ConsulError, httpx.TimeoutException) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Service is temporarily unavailable.",
        ) from error
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Service is temporarily unavailable.",
        ) from error

    if response.status_code in {401, 403}:
        raise HTTPException(
            status_code=response.status_code,
            detail="Authentication with User Service was rejected.",
        )
    if response.status_code == 404:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user was not found.",
        )
    if response.status_code >= 500:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User Service is temporarily unavailable.",
        )
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication with User Service was rejected.",
        )
    return response.json()
