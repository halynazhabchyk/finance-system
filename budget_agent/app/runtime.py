"""budget-agent application factory: Agent Card, A2A JSON-RPC endpoint, health check, Consul."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
from starlette.applications import Starlette

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from shared.ai_tools.a2a.server import create_agent_app
from shared.ai_tools.a2a.server.wiring import configure_logging, jwt_verifier, lazy_llm_factory
from shared.ai_tools.gateway.factory import gateway_client_factory
from shared.ai_tools.llm import LLMClient
from shared.service_discovery.consul import ServiceConfig

from app.a2a_server.agent_card import AGENT_NAME, build_budget_agent_card
from app.a2a_server.executor import build_executor
from app.core.config import get_settings
from app.integrations.budget_api import BudgetAgentApiClient

SERVICE_PORT = 8041


def create_app(
    *,
    api_transport: httpx.AsyncBaseTransport | None = None,
    llm: LLMClient | None = None,
    sleep=None,
) -> Starlette:
    """``api_transport``, ``llm`` and ``sleep`` are injected by tests (no network, no real model)."""
    configure_logging()
    settings = get_settings()
    api_client = gateway_client_factory(settings.gateway, client_class=BudgetAgentApiClient, transport=api_transport)

    return create_agent_app(
        card=build_budget_agent_card(settings.public_url),
        executor=build_executor(
            api_client_factory=api_client,
            llm_factory=lazy_llm_factory(settings.llm, llm),
            limits=settings.limits,
            saga_wait_seconds=settings.saga_wait_seconds,
            saga_poll_interval_seconds=settings.saga_poll_interval_seconds,
            sleep=sleep,
        ),
        verifier=jwt_verifier(api_client),
        service_config=ServiceConfig.from_env(AGENT_NAME, SERVICE_PORT),
    )
