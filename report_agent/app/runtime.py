"""report-agent application factory: Agent Card, A2A JSON-RPC endpoint, health check, Consul."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from starlette.applications import Starlette

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from shared.ai_tools.a2a.client import RemoteAgentClient
from shared.ai_tools.a2a.server import create_agent_app
from shared.ai_tools.a2a.server.wiring import configure_logging, jwt_verifier, lazy_llm_factory
from shared.ai_tools.gateway.factory import gateway_client_factory
from shared.ai_tools.llm import LLMClient
from shared.service_discovery.consul import ServiceConfig

from app.a2a_server.agent_card import AGENT_NAME, build_report_agent_card
from app.a2a_server.executor import build_executor
from app.core.config import get_settings

SERVICE_PORT = 8042


def create_app(
    *,
    api_transport: httpx.AsyncBaseTransport | None = None,
    budget_agent_transport: httpx.AsyncBaseTransport | None = None,
    llm: LLMClient | None = None,
) -> Starlette:
    """Transports and ``llm`` are injected by tests (no network, no real model)."""
    configure_logging()
    settings = get_settings()
    api_client = gateway_client_factory(settings.gateway, transport=api_transport)

    def remote_budget_agent(token: str) -> RemoteAgentClient:
        # The user's JWT is forwarded to budget-agent (requirement 5.8).
        return RemoteAgentClient(
            base_url=settings.budget_agent_url,
            access_token=token,
            timeout_seconds=settings.a2a_timeout_seconds,
            transport=budget_agent_transport,
        )

    return create_agent_app(
        card=build_report_agent_card(settings.public_url),
        executor=build_executor(
            api_client_factory=api_client,
            remote_factory=remote_budget_agent,
            llm_factory=lazy_llm_factory(settings.llm, llm),
            limits=settings.limits,
        ),
        verifier=jwt_verifier(api_client),
        service_config=ServiceConfig.from_env(AGENT_NAME, SERVICE_PORT),
    )
