"""Budget Service application factory and lifecycle."""

from __future__ import annotations

import logging
import sys
import os
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.api.exception_handlers import register_exception_handlers
from app.api.routers import budgets, categories, expenses, system
from shared.web.openapi import install_public_openapi
from shared.service_discovery.consul import ServiceConfig, service_registration
from app.workers.outbox_publisher import OutboxPublisher
from app.workers.saga_dlq_consumer import SagaDlqConsumer
from app.workers.saga_reply_consumer import SagaReplyConsumer
from app.workers.saga_timeout_watcher import SagaTimeoutWatcher


def configure_logging() -> None:
    """Root handler so shared.messaging INFO logs (receive/retry/DLQ) are visible."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app() -> FastAPI:
    configure_logging()
    service_config = ServiceConfig.from_env("budget-service", 8002)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with service_registration(service_config):
            stop_event = asyncio.Event()
            # Consumers run in their own threads; the polling workers are
            # asyncio tasks that offload DB work, so HTTP handling is not blocked.
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
    app.include_router(categories.router)
    app.include_router(expenses.router)
    return app
