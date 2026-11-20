"""RabbitMQ configuration loaded from environment variables."""

from __future__ import annotations

import os


def rabbitmq_url() -> str:
    return os.getenv(
        "RABBITMQ_URL",
        "******rabbitmq:5672/%2F",
    )


def rabbitmq_exchange() -> str:
    return os.getenv("RABBITMQ_EXCHANGE", "finance.events")


def publish_retries() -> int:
    return max(1, int(os.getenv("RABBITMQ_PUBLISH_RETRIES", "3")))


def max_delivery_attempts() -> int:
    return max(1, int(os.getenv("RABBITMQ_MAX_DELIVERY_ATTEMPTS", "3")))


def retry_delay_seconds() -> int:
    return max(1, int(os.getenv("RABBITMQ_RETRY_DELAY_SECONDS", "5")))
