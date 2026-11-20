"""Entry point of the MCP server."""

from __future__ import annotations

import sys
from pathlib import Path

# Script mode (MCP Inspector runs this file directly): make the 'app' package importable.
_SERVICE_ROOT = str(Path(__file__).resolve().parents[1])
if _SERVICE_ROOT not in sys.path:
    sys.path.insert(0, _SERVICE_ROOT)

import uvicorn

from shared.log import configure_logging
from shared.service_discovery.consul import ServiceConfig, gateway_route_tags, service_registration

from app.core.config import McpSettings
from ai_tools.gateway.factory import gateway_client_factory

from app.core.context import McpDependencies
from app.http_app import create_http_app
from app.server import build_server


# The MCP endpoint keeps its path.
GATEWAY_TAGS = gateway_route_tags("mcp-server", "/mcp", strip_prefix=False)

SERVICE_NAME = "mcp-server"


def main() -> None:
    # stdout is the protocol channel of the stdio transport: logs go to stderr.
    configure_logging(stream=sys.stderr)
    settings = McpSettings.from_env()
    server = build_server(McpDependencies(settings, gateway_client_factory(settings.gateway)))

    if settings.transport == "stdio":
        server.run("stdio")
        return

    service_config = ServiceConfig.from_env(SERVICE_NAME, settings.port, GATEWAY_TAGS)
    with service_registration(service_config):
        uvicorn.run(create_http_app(server, settings), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
