"""AI Assistant application factory and lifecycle."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.log import configure_logging

from app.api.exception_handlers import register_exception_handlers
from app.api.routers import chat, system
from shared.service_discovery.consul import ServiceConfig, api_route_tags, service_registration
from shared.web.openapi import install_public_openapi
from shared.security.cors import install_cors
from shared.security.openapi import swagger_ui_oauth_config
from app.api.dependencies import SERVICE_SCOPES


GATEWAY_TAGS = api_route_tags("ai-assistant", "/api/assistant", "/internal/assistant")

SERVICE_NAME = "ai-assistant"
SERVICE_PORT = 8020


def create_app() -> FastAPI:
    configure_logging()
    service_config = ServiceConfig.from_env(SERVICE_NAME, SERVICE_PORT, GATEWAY_TAGS)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            yield

    app = FastAPI(
        title="AI Assistant",
        description="Natural-language access to budgets and reports through function calling.",
        lifespan=lifespan,
        root_path=os.getenv("PUBLIC_API_PREFIX", ""),
        root_path_in_servers=False,
        swagger_ui_init_oauth=swagger_ui_oauth_config(SERVICE_SCOPES),
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/assistant": os.getenv("PUBLIC_API_PREFIX", "/api/assistant"),
        },
    )
    register_exception_handlers(app)
    app.include_router(system.router)
    app.include_router(chat.router)
    install_cors(app)
    return app
