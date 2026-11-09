"""Entry point of the MCP server.

    python -m app.main                       # stdio (MCP Inspector, IDE); JWT in MCP_USER_JWT
    MCP_TRANSPORT=streamable-http python -m app.main   # Docker; JWT in the Authorization header
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allows both `python -m app.main` (from mcp_server/) and `python mcp_server/app/main.py`
# (how MCP Inspector starts a stdio server from the project root).
for path in (Path(__file__).resolve().parents[2], Path(__file__).resolve().parents[1]):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import uvicorn

from shared.service_discovery.consul import ServiceConfig, service_registration

from app.core.config import McpSettings
from shared.ai_tools.gateway.factory import gateway_client_factory

from app.core.context import McpDependencies
from app.http_app import create_http_app
from app.server import build_server

SERVICE_NAME = "mcp-server"


def main() -> None:
    # stdout is the protocol channel of the stdio transport: logs go to stderr.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = McpSettings.from_env()
    server = build_server(McpDependencies(settings, gateway_client_factory(settings.gateway)))

    if settings.transport == "stdio":
        server.run("stdio")
        return

    service_config = ServiceConfig.from_env(SERVICE_NAME, settings.port)
    with service_registration(service_config):
        uvicorn.run(create_http_app(server, settings), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
