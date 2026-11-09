"""ASGI application of an A2A agent: Agent Card, JSON-RPC endpoint, health check, Consul."""

from __future__ import annotations

from contextlib import asynccontextmanager

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from shared.ai_tools.a2a.server.auth import BearerAuthMiddleware, TokenVerifier
from shared.ai_tools.a2a.server.executor import SkillExecutor
from shared.service_discovery.consul import ServiceConfig, service_registration

RPC_PATH = "/"
HEALTH_PATH = "/internal/health"


def create_agent_app(
    *,
    card: AgentCard,
    executor: SkillExecutor,
    verifier: TokenVerifier,
    service_config: ServiceConfig,
) -> Starlette:
    """Tasks are kept in memory (``InMemoryTaskStore``): progress is delivered over one
    streaming (SSE) call, so a caller never has to come back to the same instance."""
    handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore(), agent_card=card)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @asynccontextmanager
    async def lifespan(_: Starlette):
        with service_registration(service_config):
            yield

    return Starlette(
        routes=[
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(handler, rpc_url=RPC_PATH),
            Route(HEALTH_PATH, health, methods=["GET"]),
        ],
        middleware=[Middleware(BearerAuthMiddleware, verifier=verifier, protected_paths=(RPC_PATH,))],
        lifespan=lifespan,
    )
