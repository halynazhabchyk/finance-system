"""User Service application factory and lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings

from shared.log import configure_logging

from app.api.routers import system, users
from shared.web.errors import register_domain_error_handler
from shared.web.openapi import install_public_openapi
from shared.security.cors import install_cors
from shared.security.openapi import swagger_ui_oauth_config
from app.api.dependencies import SERVICE_SCOPES
from shared.service_discovery.consul import ServiceConfig, api_route_tags, service_registration


# Only the user's own profile is public; the user list, /block and /activate stay internal.
GATEWAY_TAGS = api_route_tags(
    "user-service",
    "/api/users",
    "/internal/users",
    rule="PathRegexp(`^/api/users/[0-9a-fA-F-]{36}(/name)?$`)",
)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    service_config = ServiceConfig.from_env("user-service", 8001, GATEWAY_TAGS)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            yield

    app = FastAPI(
        title="User Service",
        lifespan=lifespan,
        root_path=settings.public_api_prefix,
        root_path_in_servers=False,
        swagger_ui_init_oauth=swagger_ui_oauth_config(SERVICE_SCOPES),
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/users": settings.public_api_prefix or "/api/users",
        },
    )
    register_domain_error_handler(app)
    app.include_router(system.router)
    app.include_router(users.router)
    install_cors(app)
    return app
