"""Swagger UI login through Keycloak: Authorization Code with PKCE."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from fastapi.security import OAuth2AuthorizationCodeBearer

DEFAULT_PUBLIC_ISSUER = "http://localhost:8080/auth/realms/finance"
DEFAULT_SWAGGER_CLIENT_ID = "finance-swagger"

# Client scopes of the realm "finance" (keycloak/realm-export.json).
SCOPE_DESCRIPTIONS: dict[str, str] = {
    "users:read": "Read your own profile (User Service)",
    "users:write": "Change your own profile (User Service)",
    "budgets:read": "Read budgets, categories and expenses (Budget Service)",
    "budgets:write": "Create and change budgets, categories and expenses (Budget Service)",
    "reports:read": "Read monthly and annual reports (Report Service)",
    "assistant:chat": "Talk to the AI assistant (ai-assistant)",
}


def public_issuer() -> str:
    """Public issuer (iss claim)."""
    return os.getenv("OIDC_ISSUER", DEFAULT_PUBLIC_ISSUER).rstrip("/")


def swagger_client_id() -> str:
    return os.getenv("OIDC_SWAGGER_CLIENT_ID", DEFAULT_SWAGGER_CLIENT_ID)


def authorization_code_scheme(service_scopes: Sequence[str], *, auto_error: bool = True) -> OAuth2AuthorizationCodeBearer:
    """OAuth2 Authorization Code scheme of a service."""
    unknown = [scope for scope in service_scopes if scope not in SCOPE_DESCRIPTIONS]
    if unknown:
        raise ValueError(f"Unknown OAuth scopes: {unknown}")
    issuer = public_issuer()
    return OAuth2AuthorizationCodeBearer(
        authorizationUrl=f"{issuer}/protocol/openid-connect/auth",
        tokenUrl=f"{issuer}/protocol/openid-connect/token",
        scopes={scope: SCOPE_DESCRIPTIONS[scope] for scope in service_scopes},
        auto_error=auto_error,
        description="Sign in through Keycloak (Authorization Code + PKCE). Read scopes are granted by default; "
        "tick write scopes only when you need to change data.",
    )


def swagger_ui_oauth_config(service_scopes: Sequence[str]) -> dict[str, Any]:
    """Swagger UI OAuth settings: client, PKCE, preselected scopes."""
    preselected = [scope for scope in service_scopes if not scope.endswith(":write")]
    return {
        "clientId": swagger_client_id(),
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": " ".join(preselected),
    }
