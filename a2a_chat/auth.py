"""Keycloak access token for the A2A chat: from A2A_ACCESS_TOKEN or a hidden prompt; never printed."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import jwt

TOKEN_ENV = "A2A_ACCESS_TOKEN"
HOW_TO_GET = (
    "Отримайте новий токен: Swagger UI (http://localhost:8080/api/budgets/docs) → Authorize → "
    "вхід через Keycloak; скопіюйте Bearer-токен із запиту (Copy as curl / DevTools → Network)."
)
REJECTED = "Токен недійсний або прострочений. " + HOW_TO_GET


class TokenProblem(Exception):
    """The token cannot be used; the message is safe to show to the user."""


@dataclass(frozen=True)
class TokenInfo:
    subject: str
    expires_at: int
    scopes: frozenset[str]
    username: str | None = None

    def minutes_left(self, now: float | None = None) -> int:
        return max(0, int((self.expires_at - (now if now is not None else time.time())) // 60))


def read_token(env_value: str | None, read_secret: Callable[[str], str]) -> str:
    """Token from the environment variable, otherwise from a hidden prompt."""
    token = (env_value or "").strip() or read_secret("Access token (Keycloak): ").strip()
    if token.lower().startswith("bearer "):
        token = token[len("bearer ") :].strip()
    if not token:
        raise TokenProblem(f"Токен не вказано. Задайте {TOKEN_ENV} або вставте токен. " + HOW_TO_GET)
    return token


def inspect_token(token: str, *, now: float | None = None) -> TokenInfo:
    """Claims for display; a malformed or expired token is reported before any request."""
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.InvalidTokenError as error:
        raise TokenProblem("Це не JWT access token. " + HOW_TO_GET) from error

    subject, expires_at = claims.get("sub"), claims.get("exp")
    if not isinstance(subject, str) or not isinstance(expires_at, (int, float)):
        raise TokenProblem("У токені немає sub або exp. " + HOW_TO_GET)
    if expires_at <= (now if now is not None else time.time()):
        raise TokenProblem("Строк дії токена минув (15 хв). " + HOW_TO_GET)
    scope = claims.get("scope")
    return TokenInfo(
        subject=subject,
        expires_at=int(expires_at),
        scopes=frozenset(scope.split()) if isinstance(scope, str) else frozenset(),
        username=claims.get("preferred_username") or claims.get("email"),
    )
