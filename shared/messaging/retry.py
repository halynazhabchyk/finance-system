"""RabbitMQ retry and dead-letter routing."""

from __future__ import annotations

import logging

import pika

logger = logging.getLogger(__name__)


def publish_retry(
    channel,
    topology,
    body: bytes,
    properties,
    routing_key: str,
    attempt: int,
    retry_delay: int,
) -> None:
    headers = dict(properties.headers or {}) if properties else {}
    headers["x-delivery-attempt"] = attempt
    channel.basic_publish(
        exchange=topology.retry_exchange,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(
            content_type=(
                properties.content_type
                if properties
                else "application/json"
            ),
            delivery_mode=2,
            message_id=properties.message_id if properties else None,
            type=properties.type if properties else routing_key,
            headers=headers,
        ),
    )
    logger.warning(
        "Scheduled RabbitMQ retry for %s in %ss (attempt %s).",
        routing_key,
        retry_delay,
        attempt,
    )


def publish_dead_letter(
    channel,
    topology,
    body: bytes,
    properties,
    routing_key: str,
) -> None:
    channel.basic_publish(
        exchange=topology.dlq_exchange,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(
            content_type=(
                properties.content_type
                if properties
                else "application/json"
            ),
            delivery_mode=2,
            message_id=properties.message_id if properties else None,
            type=properties.type if properties else routing_key,
            headers={"x-dead-letter-reason": "processing_failed"},
        ),
    )
    logger.error(
        "Moved RabbitMQ event %s to DLQ %s.",
        routing_key,
        topology.dlq_name,
    )
