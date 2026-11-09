"""AI Assistant application factory and lifecycle."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.api.exception_handlers import register_exception_handlers
from app.api.routers import chat, system
from shared.service_discovery.consul import ServiceConfig, service_registration
from shared.web.openapi import install_public_openapi

SERVICE_NAME = "ai-assistant"
SERVICE_PORT = 8020


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    configure_logging()
    service_config = ServiceConfig.from_env(SERVICE_NAME, SERVICE_PORT)

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
    return app
