"""Budget Service application factory and lifecycle."""

from __future__ import annotations

import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.api.exception_handlers import register_exception_handlers
from app.api.routers import budgets, system
from shared.web.openapi import install_public_openapi
from shared.service_discovery.consul import ServiceConfig, service_registration


def create_app() -> FastAPI:
    service_config = ServiceConfig.from_env("budget-service", 8002)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            yield

    app = FastAPI(
        title="Budget Service",
        lifespan=lifespan,
        root_path=os.getenv("PUBLIC_API_PREFIX", ""),
        root_path_in_servers=False,
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/budgets": os.getenv("PUBLIC_API_PREFIX", "/api/budgets"),
        },
    )
    register_exception_handlers(app)
    app.include_router(system.router)
    app.include_router(budgets.router)
    return app
