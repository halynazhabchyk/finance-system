"""Scheduler configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SchedulerConfig:
    service_port: int
    health_bind_host: str
    daily_time: str
    monthly_time: str
    timezone: str
    rabbitmq_url: str
    rabbitmq_exchange: str
    rabbitmq_publish_retries: int
    rabbitmq_reconnect_interval_seconds: float

    @classmethod
    def from_env(cls) -> SchedulerConfig:
        return cls(
            service_port=int(os.getenv("SERVICE_PORT", "8010")),
            health_bind_host=os.getenv("HEALTH_BIND_HOST", "0.0.0.0"),
            daily_time=os.getenv("SCHEDULER_DAILY_TIME", "23:00"),
            monthly_time=os.getenv("SCHEDULER_MONTHLY_TIME", "23:30"),
            timezone=os.getenv("SCHEDULER_TIMEZONE", "Europe/Kyiv"),
            rabbitmq_url=os.getenv(
                "RABBITMQ_URL",
                "amqp://guest:guest@rabbitmq:5672/%2F",
            ),
            rabbitmq_exchange=os.getenv(
                "RABBITMQ_EXCHANGE",
                "finance.events",
            ),
            rabbitmq_publish_retries=int(
                os.getenv("RABBITMQ_PUBLISH_RETRIES", "3")
            ),
            rabbitmq_reconnect_interval_seconds=float(
                os.getenv("RABBITMQ_RECONNECT_INTERVAL_SECONDS", "5")
            ),
        )
