"""HTTP failures of the public API, translated into messages an LLM can act on."""

from __future__ import annotations

import re
from typing import Any

MAX_DETAIL_CHARS = 300

_MESSAGES: dict[int, str] = {
    401: "Authentication failed: the user's access token is missing, invalid or expired. "
    "Tell the user to log in again. Do not retry.",
    403: "Access denied: the account is blocked or the resource belongs to another user. Do not retry.",
    404: "Not found: {detail}. The identifier may be wrong or the data does not exist yet. "
    "Do not invent identifiers; look them up with a tool or ask the user.",
    409: "Conflict with the current state: {detail}.",
    422: "The service rejected the data: {detail}. Correct the arguments or ask the user.",
}
# ЛР №5, п. 4–5: a valid token without the needed OAuth scope (RFC 6750 "insufficient_scope").
# Kept apart from the generic 403 so the model does not blame a blocked account or another user's data.
_INSUFFICIENT_SCOPE = (
    "Permission missing: the user's access token does not include the scope \"{scope}\" required for this "
    "operation. Tell the user to sign in again and grant \"{scope}\" (Swagger: Authorize, tick the scope). Do not retry."
)
_SCOPE_IN_CHALLENGE = re.compile(r'error="insufficient_scope"(?:.*?scope="([^"]*)")?')
_SERVER_ERROR = "The finance service is temporarily unavailable (HTTP {status}). Try again later."
_TIMEOUT = "The finance service did not respond in time. Try again later."
_NETWORK = "The finance service is unreachable. Try again later."


class GatewayError(Exception):
    """A request to the public API failed.

    ``llm_message`` is safe to show to the model and the user: it contains the
    service ``detail`` (already client-safe) but no tokens or internal URLs.
    """

    def __init__(self, status_code: int | None, llm_message: str) -> None:
        super().__init__(llm_message)
        self.status_code = status_code
        self.llm_message = llm_message

    @classmethod
    def from_response(cls, status_code: int, body: Any, www_authenticate: str | None = None) -> GatewayError:
        if status_code >= 500:
            return cls(status_code, _SERVER_ERROR.format(status=status_code))
        if status_code == 403 and www_authenticate:
            match = _SCOPE_IN_CHALLENGE.search(www_authenticate)
            if match:
                return InsufficientScope(match.group(1) or "unknown")
        template = _MESSAGES.get(status_code, "The request failed with HTTP {status}: {detail}.")
        return cls(status_code, template.format(status=status_code, detail=summarize_detail(body)))

    @classmethod
    def timeout(cls) -> GatewayError:
        return cls(None, _TIMEOUT)

    @classmethod
    def network(cls) -> GatewayError:
        return cls(None, _NETWORK)


class InsufficientScope(GatewayError):
    """403 with ``WWW-Authenticate: Bearer error="insufficient_scope"`` – the token lacks a scope."""

    def __init__(self, scope: str) -> None:
        super().__init__(403, _INSUFFICIENT_SCOPE.format(scope=scope))
        self.scope = scope


def summarize_detail(body: Any) -> str:
    """Short, human readable form of a FastAPI ``detail`` (string or validation list)."""
    detail = body.get("detail") if isinstance(body, dict) else body
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                location = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
                parts.append(f"{location}: {item.get('msg', 'invalid value')}" if location else str(item.get("msg")))
            else:
                parts.append(str(item))
        text = "; ".join(parts)
    elif detail is None:
        text = "no details"
    else:
        text = str(detail)
    return text[:MAX_DETAIL_CHARS]
