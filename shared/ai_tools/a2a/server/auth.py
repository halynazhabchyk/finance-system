"""JWT check of A2A calls before a task is created (guardrail of requirement 5.8).

The Agent Card stays public (discovery); the JSON-RPC endpoint requires
``Authorization: Bearer <JWT>``, verified through User Service via the gateway.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from shared.ai_tools.gateway.client import AccountBlocked, AuthenticationFailed
from shared.ai_tools.gateway.errors import GatewayError

logger = logging.getLogger(__name__)

TokenVerifier = Callable[[str], Awaitable[None]]


class BearerAuthMiddleware:
    """Pure ASGI middleware (does not buffer SSE streams)."""

    def __init__(self, app: ASGIApp, *, verifier: TokenVerifier, protected_paths: tuple[str, ...] = ("/",)) -> None:
        self.app = app
        self.verifier = verifier
        self.protected_paths = protected_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or _route_path(scope) not in self.protected_paths:
            await self.app(scope, receive, send)
            return
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        scheme, _, token = headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            await _reject(send, 401, "Bearer access token is required.")
            return
        try:
            await self.verifier(token.strip())
        except AuthenticationFailed:
            logger.warning("a2a_auth_rejected reason=invalid_token path=%s", scope["path"])
            await _reject(send, 401, "Invalid or expired access token.")
            return
        except AccountBlocked:
            logger.warning("a2a_auth_rejected reason=account_blocked path=%s", scope["path"])
            await _reject(send, 403, "The user account is blocked.")
            return
        except GatewayError as error:
            await _reject(send, 503, error.llm_message)
            return
        await self.app(scope, receive, send)


def _route_path(scope: Scope) -> str:
    """Path inside the app: when mounted under a prefix, Starlette keeps it in ``root_path``."""
    path, root = scope["path"], scope.get("root_path", "")
    if root and path.startswith(root):
        path = path[len(root):]
    return path or "/"


async def _reject(send: Send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    if status == 401:
        headers.append((b"www-authenticate", b"Bearer"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})
