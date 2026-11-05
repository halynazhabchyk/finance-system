"""FastAPI application lifecycle for Scheduler."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.service_discovery.consul import ServiceConfig, service_registration

from app.config import SchedulerConfig
from app.health import Readiness, create_router
from app.publisher import EventPublisher
from app.scheduler import ReportScheduler

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    config = SchedulerConfig.from_env()
    readiness = Readiness()
    publisher = EventPublisher(config)
    report_scheduler = ReportScheduler(
        publisher,
        config.timezone,
        config.daily_time,
        config.monthly_time,
    )
    service_config = ServiceConfig.from_env("scheduler", config.service_port)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        registration = service_registration(service_config)
        reconnect_task: asyncio.Task[None] | None = None

        async def connect_until_ready() -> None:
            while True:
                try:
                    await publisher.connect()
                    readiness.rabbitmq_available = publisher.available
                    if readiness.rabbitmq_available:
                        report_scheduler.start()
                        readiness.scheduler_running = True
                        logger.info("Scheduler is ready.")
                        return
                except Exception:
                    readiness.rabbitmq_available = False
                    logger.exception(
                        "RabbitMQ is unavailable. Retrying connection in %.1f seconds.",
                        config.rabbitmq_reconnect_interval_seconds,
                    )
                await asyncio.sleep(config.rabbitmq_reconnect_interval_seconds)

        try:
            registration.__enter__()
            reconnect_task = asyncio.create_task(connect_until_ready())
            yield
        finally:
            if reconnect_task is not None:
                reconnect_task.cancel()
                await asyncio.gather(reconnect_task, return_exceptions=True)
            readiness.scheduler_running = False
            await report_scheduler.shutdown()
            await publisher.close()
            registration.__exit__(None, None, None)

    app = FastAPI(title="Scheduler", lifespan=lifespan)
    app.include_router(create_router(readiness))
    return app
