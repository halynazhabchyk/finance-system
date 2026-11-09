"""Dependency injection of the AI Assistant API."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from shared.ai_tools.gateway.factory import gateway_client_factory
from shared.ai_tools.llm.factory import create_llm_client

from app.core.config import get_settings
from app.services.chat_service import AssistantChatService

# Same scheme as User/Budget/Report Service: Swagger UI asks for login and password,
# obtains the JWT from User Service and sends it as "Authorization: Bearer <token>".
# auto_error=False keeps our own 401 response below.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=os.getenv("PUBLIC_AUTH_URL", "/api/users/auth/login"),
    auto_error=False,
    description="Log in with User Service credentials; the access token is sent as Bearer.",
)


def get_access_token(token: Annotated[str | None, Depends(oauth2_scheme)]) -> str:
    """The raw JWT of the caller; it is forwarded to the services and never logged."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@lru_cache
def get_chat_service() -> AssistantChatService:
    """One stateless service per process (the LLM client keeps a connection pool)."""
    settings = get_settings()
    return AssistantChatService(
        llm=create_llm_client(settings.llm),
        limits=settings.limits,
        api_client_factory=gateway_client_factory(settings.gateway),
    )


AccessToken = Annotated[str, Depends(get_access_token)]
ChatServiceDependency = Annotated[AssistantChatService, Depends(get_chat_service)]
