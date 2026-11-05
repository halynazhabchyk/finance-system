"""Shared RabbitMQ messaging transport."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from threading import Event, Thread
from typing import Any

import pika

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    logger.propagate = False


class RabbitMQError(RuntimeError):
    """Base error for RabbitMQ operations."""


class RabbitMQPublishError(RabbitMQError):
    """An event could not be published after retries."""


class PermanentEventError(RabbitMQError):
    """An event cannot be processed or retried."""


def rabbitmq_url() -> str:
    return os.getenv(
        "RABBITMQ_URL",
        "amqp://guest:guest@rabbitmq:5672/%2F",
    )


def publish_event(event: dict[str, Any]) -> None:
    retries = max(1, int(os.getenv("RABBITMQ_PUBLISH_RETRIES", "3")))
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        connection: pika.BlockingConnection | None = None
        try:
            parameters = pika.URLParameters(rabbitmq_url())
            parameters.connection_attempts = 3
            parameters.retry_delay = 2
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.confirm_delivery()
            exchange = os.getenv("RABBITMQ_EXCHANGE", "finance.events")
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
            logger.exception(
                "RabbitMQ publish attempt %s/%s failed for %s.",
                attempt,
                retries,
                event.get("event_type"),
            )
        finally:
            if connection and connection.is_open:
                connection.close()
    raise RabbitMQPublishError("Could not publish event to RabbitMQ.") from last_error


class EventConsumer:
    def __init__(
        self,
        queue_name: str,
        routing_keys: list[str],
        handler: Callable[[dict[str, Any]], None],
        max_delivery_attempts: int | None = None,
        retry_delay_seconds: int | None = None,
    ):
        self.queue_name = queue_name
        self.routing_keys = routing_keys
        self.handler = handler
        self.max_delivery_attempts = max_delivery_attempts or max(
            1, int(os.getenv("RABBITMQ_MAX_DELIVERY_ATTEMPTS", "3"))
        )
        self.retry_delay_seconds = retry_delay_seconds or max(
            1, int(os.getenv("RABBITMQ_RETRY_DELAY_SECONDS", "5"))
        )
        self.retry_exchange = f"{os.getenv('RABBITMQ_EXCHANGE', 'finance.events')}.retry"
        self.dlq_exchange = f"{os.getenv('RABBITMQ_EXCHANGE', 'finance.events')}.dlx"
        self.dlq_name = f"{queue_name}.dlq"
        self.retry_queue = f"{queue_name}.retry"
        self.stop_event = Event()
        self.thread: Thread | None = None
        self.connection: pika.BlockingConnection | None = None

    def start(self) -> None:
        logger.info(
            "Starting RabbitMQ consumer for queue %s (routing keys: %s).",
            self.queue_name,
            ", ".join(self.routing_keys),
        )
        self.thread = Thread(target=self._run, name="rabbitmq-consumer", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.connection and self.connection.is_open:
            try:
                self.connection.add_callback_threadsafe(
                    self.connection.close
                )
            except (OSError, pika.exceptions.AMQPError):
                pass
        if self.thread:
            self.thread.join(timeout=10)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._consume()
            except Exception:
                logger.exception(
                    "RabbitMQ consumer stopped unexpectedly for queue %s; retrying.",
                    self.queue_name,
                )
                if not self.stop_event.wait(5):
                    continue

    def _consume(self) -> None:
        parameters = pika.URLParameters(rabbitmq_url())
        parameters.connection_attempts = 3
        connection = pika.BlockingConnection(parameters)
        self.connection = connection
        channel = connection.channel()
        logger.info("RabbitMQ consumer connected to queue %s.", self.queue_name)
        exchange = os.getenv("RABBITMQ_EXCHANGE", "finance.events")
        channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
        channel.exchange_declare(
            exchange=self.retry_exchange,
            exchange_type="topic",
            durable=True,
        )
        channel.exchange_declare(
            exchange=self.dlq_exchange,
            exchange_type="topic",
            durable=True,
        )
        channel.queue_declare(queue=self.queue_name, durable=True)
        channel.queue_declare(
            queue=self.retry_queue,
            durable=True,
            arguments={
                "x-message-ttl": self.retry_delay_seconds * 1000,
                "x-dead-letter-exchange": exchange,
            },
        )
        channel.queue_bind(
            exchange=self.retry_exchange,
            queue=self.retry_queue,
            routing_key="#",
        )
        channel.queue_declare(queue=self.dlq_name, durable=True)
        channel.queue_bind(
            exchange=self.dlq_exchange,
            queue=self.dlq_name,
            routing_key="#",
        )
        for key in self.routing_keys:
            channel.queue_bind(exchange=exchange, queue=self.queue_name, routing_key=key)
        channel.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            event: dict[str, Any] | None = None
            event_type = properties.type if properties else "unknown"
            delivery_attempt = int(
                (properties.headers or {}).get("x-delivery-attempt", 0)
                if properties
                else 0
            )
            try:
                event = json.loads(body)
                event_type = event.get("event_type", event_type)
                logger.info(
                    "Received RabbitMQ event %s (%s) from queue %s.",
                    event.get("event_id", "unknown"),
                    event_type,
                    self.queue_name,
                )
                self.handler(event)
            except PermanentEventError:
                logger.exception(
                    "Permanent RabbitMQ event failure; sending %s to DLQ.",
                    event_type,
                )
                self._publish_dead_letter(ch, body, properties, event_type)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(
                    "Acknowledged RabbitMQ event %s (%s) from queue %s.",
                    event.get("event_id", "unknown") if event else "unknown",
                    event_type,
                    self.queue_name,
                )
                return
            except Exception:
                logger.exception(
                    "RabbitMQ event handling failed for %s (attempt %s/%s).",
                    event_type,
                    delivery_attempt + 1,
                    self.max_delivery_attempts,
                )
                try:
                    if delivery_attempt + 1 >= self.max_delivery_attempts:
                        self._publish_dead_letter(ch, body, properties, event_type)
                    else:
                        self._publish_retry(
                            ch,
                            body,
                            properties,
                            event_type,
                            delivery_attempt + 1,
                        )
                except Exception:
                    logger.exception(
                        "Could not route failed RabbitMQ event %s; requeueing.",
                        event_type,
                    )
                    ch.basic_nack(
                        delivery_tag=method.delivery_tag,
                        requeue=True,
                    )
                    return
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(
                "Acknowledged RabbitMQ event %s (%s) from queue %s.",
                event.get("event_id", "unknown") if event else "unknown",
                event_type,
                self.queue_name,
            )

        channel.basic_consume(queue=self.queue_name, on_message_callback=callback)
        channel.start_consuming()

    def _publish_retry(self, channel, body, properties, routing_key, attempt):
        headers = dict(properties.headers or {}) if properties else {}
        headers["x-delivery-attempt"] = attempt
        channel.basic_publish(
            exchange=self.retry_exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type=properties.content_type if properties else "application/json",
                delivery_mode=2,
                message_id=properties.message_id if properties else None,
                type=properties.type if properties else routing_key,
                headers=headers,
            ),
        )
        logger.warning(
            "Scheduled RabbitMQ retry for %s in %ss (attempt %s).",
            routing_key,
            self.retry_delay_seconds,
            attempt,
        )

    def _publish_dead_letter(self, channel, body, properties, routing_key):
        channel.basic_publish(
            exchange=self.dlq_exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type=properties.content_type if properties else "application/json",
                delivery_mode=2,
                message_id=properties.message_id if properties else None,
                type=properties.type if properties else routing_key,
                headers={"x-dead-letter-reason": "processing_failed"},
            ),
        )
        logger.error("Moved RabbitMQ event %s to DLQ %s.", routing_key, self.dlq_name)
