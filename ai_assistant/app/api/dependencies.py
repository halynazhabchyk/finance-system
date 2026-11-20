"""Dependency injection of the AI Assistant API."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Security

from ai_tools.gateway.factory import gateway_client_factory
from ai_tools.llm.factory import create_llm_client
from shared.security.fastapi import bearer_token_dependency
from shared.security.jwt import VerifiedToken
from shared.security.openapi import authorization_code_scheme

from app.core.config import get_settings
from app.services.chat_service import AssistantChatService

# Swagger UI signs in through Keycloak (Authorization Code + PKCE).
SERVICE_SCOPES = ["assistant:chat"]
oauth2_scheme = authorization_code_scheme(SERVICE_SCOPES, auto_error=False)
verified_token = bearer_token_dependency(oauth2_scheme)


def get_access_token(token: Annotated[VerifiedToken, Security(verified_token, scopes=["assistant:chat"])]) -> str:
    """Verified token of the caller, forwarded unchanged."""
    return token.raw


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
