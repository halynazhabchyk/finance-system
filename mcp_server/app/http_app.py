"""Streamable HTTP application of the MCP server (Docker, behind Traefik at /mcp)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from app.core.config import McpSettings


def create_http_app(server: MCPServer, settings: McpSettings) -> Starlette:
    """``stateless_http``: no MCP session lives in process memory, so several
    instances can run behind Traefik and any of them can serve any request."""
    return server.streamable_http_app(
        streamable_http_path=settings.http_path,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(settings.allowed_hosts),
            allowed_origins=list(settings.allowed_origins),
        ),
        host="0.0.0.0",
    )
