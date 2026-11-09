"""Dependencies of the MCP handlers: how to build an API client for the current request."""

from __future__ import annotations

from dataclasses import dataclass

from mcp.server.mcpserver import Context

from shared.ai_tools.gateway import FinanceApiClient
from shared.ai_tools.gateway.factory import ApiClientFactory

from app.core.auth import resolve_access_token
from app.core.config import McpSettings


@dataclass(frozen=True)
class McpDependencies:
    settings: McpSettings
    api_client_factory: ApiClientFactory

    def api_client(self, ctx: Context) -> FinanceApiClient:
        """A client acting with the JWT of the user who sent this MCP request."""
        return self.api_client_factory(resolve_access_token(ctx.headers))

