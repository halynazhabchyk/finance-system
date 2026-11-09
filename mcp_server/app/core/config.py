"""Settings of the MCP server (environment variables only)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from shared.ai_tools.config import AgentLimits, ConfigurationError, GatewaySettings

Transport = Literal["stdio", "streamable-http"]


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class McpSettings:
    transport: Transport
    port: int
    http_path: str
    gateway: GatewaySettings
    result_max_chars: int
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> McpSettings:
        transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
        if transport not in ("stdio", "streamable-http"):
            raise ConfigurationError("MCP_TRANSPORT must be 'stdio' or 'streamable-http'.")
        return cls(
            transport=transport,  # type: ignore[arg-type]
            port=int(os.getenv("SERVICE_PORT", "8030")),
            http_path=os.getenv("MCP_HTTP_PATH", "/mcp"),
            gateway=GatewaySettings.from_env(),
            result_max_chars=AgentLimits.from_env().tool_result_max_chars,
            # DNS-rebinding protection of Streamable HTTP: requests come through Traefik.
            allowed_hosts=_csv("MCP_ALLOWED_HOSTS", "localhost:*,127.0.0.1:*,traefik,traefik:*,mcp-server:*"),
            allowed_origins=_csv("MCP_ALLOWED_ORIGINS", "http://localhost:*,http://127.0.0.1:*"),
        )
