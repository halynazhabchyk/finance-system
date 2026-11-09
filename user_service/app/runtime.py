"""User Service application factory and lifecycle."""

from __future__ import annotations

import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.api.routers import auth, system, users
from shared.web.errors import register_domain_error_handler
from shared.web.openapi import install_public_openapi
from shared.service_discovery.consul import ServiceConfig, service_registration


def create_app() -> FastAPI:
    service_config = ServiceConfig.from_env("user-service", 8001)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            yield

    app = FastAPI(
        title="User Service",
        lifespan=lifespan,
        root_path=os.getenv("PUBLIC_API_PREFIX", ""),
        root_path_in_servers=False,
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/users": os.getenv("PUBLIC_API_PREFIX", "/api/users"),
            "/internal/auth": f"{os.getenv('PUBLIC_API_PREFIX', '/api/users')}/auth",
        },
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8002"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_domain_error_handler(app)
    app.include_router(system.router)
    app.include_router(users.router)
    app.include_router(auth.router)
    return app
