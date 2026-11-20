"""Report Service application factory and lifecycle."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.log import configure_logging

from app.api.routers import reports, system
from app.workers.report_consumer import ReportEventConsumer
from shared.web.errors import register_domain_error_handler
from shared.web.openapi import install_public_openapi
from shared.security.cors import install_cors
from shared.security.openapi import swagger_ui_oauth_config
from app.api.dependencies import SERVICE_SCOPES
from shared.service_discovery.consul import ServiceConfig, service_registration


def create_app() -> FastAPI:
    configure_logging()
    service_config = ServiceConfig.from_env("report-service", 8003)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        consumer = ReportEventConsumer()
        with service_registration(service_config):
            consumer.start()
            try:
                yield
            finally:
                consumer.stop()

    app = FastAPI(
        title="Report Service",
        lifespan=lifespan,
        root_path=os.getenv("PUBLIC_API_PREFIX", ""),
        root_path_in_servers=False,
        swagger_ui_init_oauth=swagger_ui_oauth_config(SERVICE_SCOPES),
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/reports": os.getenv("PUBLIC_API_PREFIX", "/api/reports"),
        },
    )
    register_domain_error_handler(app)
    app.include_router(system.router)
    app.include_router(reports.router)
    install_cors(app)
    return app
