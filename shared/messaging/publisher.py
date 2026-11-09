"""RabbitMQ event publisher with publisher confirms."""

from __future__ import annotations

import json
import logging
from typing import Any

import pika

from .config import publish_retries, rabbitmq_exchange
from .connection import discard_publisher_connection, publisher_connection
from .exceptions import RabbitMQPublishError

logger = logging.getLogger(__name__)


def publish_event(event: dict[str, Any]) -> None:
    last_error: Exception | None = None
    for attempt in range(1, publish_retries() + 1):
        channel = None
        try:
            connection = publisher_connection()
            channel = connection.channel()
            channel.confirm_delivery()
            exchange = rabbitmq_exchange()
            channel.exchange_declare(
                exchange=exchange,
                exchange_type="topic",
                durable=True,
            )
            accepted = channel.basic_publish(
                exchange=exchange,
                routing_key=event["event_type"],
                body=json.dumps(event, default=str).encode(),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=event["event_id"],
                    type=event["event_type"],
                ),
                mandatory=True,
            )
            if accepted is False:
                raise RabbitMQPublishError("RabbitMQ did not confirm the event.")
            logger.info(
                "Published RabbitMQ event %s (%s).",
                event["event_id"],
                event["event_type"],
            )
            return
        except (OSError, pika.exceptions.AMQPError, RabbitMQPublishError) as error:
            last_error = error
            discard_publisher_connection()
            logger.exception(
                "RabbitMQ publish attempt %s/%s failed for %s.",
                attempt,
                publish_retries(),
                event.get("event_type"),
            )
        finally:
            if channel and channel.is_open:
                try:
                    channel.close()
                except pika.exceptions.AMQPError:
                    logger.debug("RabbitMQ publisher channel was already unavailable.")
    raise RabbitMQPublishError("Could not publish event to RabbitMQ.") from last_error
