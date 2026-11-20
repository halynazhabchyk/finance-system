"""User Service application factory and lifecycle."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routers import system, users
from shared.web.errors import register_domain_error_handler
from shared.web.openapi import install_public_openapi
from shared.security.cors import install_cors
from shared.security.openapi import swagger_ui_oauth_config
from app.api.dependencies import SERVICE_SCOPES
from shared.service_discovery.consul import ServiceConfig, service_registration


def configure_logging() -> None:
    """Root handler so INFO logs (token verification, security.token) are visible."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    configure_logging()
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
        swagger_ui_init_oauth=swagger_ui_oauth_config(SERVICE_SCOPES),
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/users": os.getenv("PUBLIC_API_PREFIX", "/api/users"),
        },
    )
    register_domain_error_handler(app)
    app.include_router(system.router)
    app.include_router(users.router)
    install_cors(app)
    return app
