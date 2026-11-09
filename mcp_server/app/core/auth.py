"""Where the user's JWT comes from (requirement 4.7).

* stdio – one local user: the token is passed in ``MCP_USER_JWT`` when the
  client (MCP Inspector, IDE) starts the server process;
* Streamable HTTP – every request carries ``Authorization: Bearer <JWT>``;
  the server is shared by many users, so a token from the environment is
  never used there.

The token is only forwarded to the REST API, where User Service verifies it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from mcp.server.mcpserver.exceptions import ToolError

MISSING_TOKEN = (
    "Authentication required: pass the user's JWT in the 'Authorization: Bearer <token>' header "
    "(HTTP) or in the MCP_USER_JWT environment variable (stdio)."
)


class MissingAccessToken(ToolError):
    """No JWT for the current request."""


def resolve_access_token(headers: Mapping[str, str] | None) -> str:
    """JWT of the current MCP request; ``headers`` is ``None`` on stdio."""
    if headers is not None:
        authorization = _header(headers, "authorization")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
        raise MissingAccessToken(MISSING_TOKEN)
    token = os.getenv("MCP_USER_JWT", "").strip()
    if not token:
        raise MissingAccessToken(MISSING_TOKEN)
    return token


def _header(headers: Mapping[str, str], name: str) -> str:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return ""
