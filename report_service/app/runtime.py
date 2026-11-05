"""Report Service application factory and lifecycle."""

from __future__ import annotations

import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.api.routers import reports, system
from app.workers.report_consumer import ReportEventConsumer
from shared.web.openapi import install_public_openapi
from shared.service_discovery.consul import ServiceConfig, service_registration


def create_app() -> FastAPI:
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
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/reports": os.getenv("PUBLIC_API_PREFIX", "/api/reports"),
        },
    )
    app.include_router(system.router)
    app.include_router(reports.router)
    return app
