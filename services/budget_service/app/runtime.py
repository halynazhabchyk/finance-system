"""Budget Service application factory and lifecycle."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings

from shared.log import configure_logging

from app.api.exception_handlers import register_exception_handlers
from app.api.routers import budgets, categories, expenses, system
from shared.web.openapi import install_public_openapi
from shared.security.cors import install_cors
from shared.security.openapi import swagger_ui_oauth_config
from app.api.dependencies import SERVICE_SCOPES
from shared.service_discovery.consul import ServiceConfig, service_registration
from app.workers.outbox_publisher import OutboxPublisher
from app.workers.saga_dlq_consumer import SagaDlqConsumer
from app.workers.saga_reply_consumer import SagaReplyConsumer
from app.workers.saga_timeout_watcher import SagaTimeoutWatcher


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    service_config = ServiceConfig.from_env("budget-service", 8002)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            stop_event = asyncio.Event()
            # Consumers run in threads, pollers as asyncio tasks.
            reply_consumer = SagaReplyConsumer()
            dlq_consumer = SagaDlqConsumer()
            reply_consumer.start()
            dlq_consumer.start()
            background_tasks = [
                asyncio.create_task(
                    OutboxPublisher().run(stop_event),
                    name="budget-outbox-publisher",
                ),
                asyncio.create_task(
                    SagaTimeoutWatcher().run(stop_event),
                    name="budget-saga-timeout-watcher",
                ),
            ]
            try:
                yield
            finally:
                stop_event.set()
                await asyncio.gather(*background_tasks, return_exceptions=True)
                reply_consumer.stop()
                dlq_consumer.stop()

    app = FastAPI(
        title="Budget Service",
        lifespan=lifespan,
        root_path=settings.public_api_prefix,
        root_path_in_servers=False,
        swagger_ui_init_oauth=swagger_ui_oauth_config(SERVICE_SCOPES),
    )
    install_public_openapi(
        app,
        path_mappings={
            "/internal/budgets": settings.public_api_prefix or "/api/budgets",
        },
    )
    register_exception_handlers(app)
    app.include_router(system.router)
    app.include_router(budgets.router)
    app.include_router(categories.router)
    app.include_router(expenses.router)
    install_cors(app)
    return app
