"""Swagger UI login through Keycloak: OAuth 2.0 Authorization Code with PKCE (ЛР №5, requirement 2.6).

The "Authorize" button sends the browser to the Keycloak login page (where
"Sign in with Google" is available) instead of asking for a password in Swagger.
Each service declares only the scopes of its own resources; the user sees and
picks them in the dialog (requirement 4.5). Read scopes are preselected, write
scopes must be ticked explicitly (least privilege).
"""

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
    """Issuer as the browser sees it (``iss`` claim); the login and token endpoints live under it."""
    return os.getenv("OIDC_ISSUER", DEFAULT_PUBLIC_ISSUER).rstrip("/")


def swagger_client_id() -> str:
    return os.getenv("OIDC_SWAGGER_CLIENT_ID", DEFAULT_SWAGGER_CLIENT_ID)


def authorization_code_scheme(service_scopes: Sequence[str], *, auto_error: bool = True) -> OAuth2AuthorizationCodeBearer:
    """Security scheme of a service: reads ``Authorization: Bearer`` and documents the Keycloak flow."""
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
    """``FastAPI(swagger_ui_init_oauth=...)``: public client, PKCE on, read scopes preselected."""
    preselected = [scope for scope in service_scopes if not scope.endswith(":write")]
    return {
        "clientId": swagger_client_id(),
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": " ".join(preselected),
    }
