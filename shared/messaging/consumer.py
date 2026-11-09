"""RabbitMQ event consumer.

Two delivery modes:

* retry topology (default) - a failed message goes to ``<queue>.retry``
  (TTL, then back to the main exchange); after ``max_delivery_attempts``
  or on ``PermanentEventError`` it goes to the dead-letter exchange;
* simple - the queue is bound to one exchange only, a failed message is
  requeued with ``nack`` after a pause, a permanent failure is dropped.

In both modes the message is acknowledged only after the handler returned
(or after the failure was routed), so a crash never loses a message.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from functools import partial
from threading import Event, Thread
from typing import Any

import pika

from .config import (
    max_delivery_attempts as configured_max_delivery_attempts,
    rabbitmq_exchange,
    retry_delay_seconds as configured_retry_delay_seconds,
)
from .connection import consumer_connection
from .exceptions import PermanentEventError
from .retry import publish_dead_letter, publish_retry
from .topology import ConsumerTopology, declare_consumer_topology, declare_simple_topology

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], None]
DELIVERY_ATTEMPT_HEADER = "x-delivery-attempt"
RECONNECT_DELAY_SECONDS = 5


def delivery_attempt(properties) -> int:
    """How many times the message was already retried (0 for the first delivery)."""
    if not properties:
        return 0
    return int((properties.headers or {}).get(DELIVERY_ATTEMPT_HEADER, 0))


class EventConsumer:
    def __init__(
        self,
        queue_name: str,
        routing_keys: list[str],
        handler: EventHandler,
        max_delivery_attempts: int | None = None,
        retry_delay_seconds: int | None = None,
        *,
        exchange: str | None = None,
        use_retry_topology: bool = True,
        thread_name: str = "rabbitmq-consumer",
    ):
        self.queue_name = queue_name
        self.routing_keys = routing_keys
        self.handler = handler
        self.max_delivery_attempts = max_delivery_attempts or configured_max_delivery_attempts()
        self.retry_delay_seconds = retry_delay_seconds or configured_retry_delay_seconds()
        # Simple mode: bind to any exchange, retry failures with nack/requeue.
        self.exchange = exchange
        self.use_retry_topology = use_retry_topology
        self.thread_name = thread_name
        self.stop_event = Event()
        self.thread: Thread | None = None
        self.connection: pika.BlockingConnection | None = None

    # --- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        logger.info(
            "Starting RabbitMQ consumer for queue %s (routing keys: %s).",
            self.queue_name,
            ", ".join(self.routing_keys),
        )
        self.thread = Thread(target=self._run, name=self.thread_name, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.connection and self.connection.is_open:
            try:
                self.connection.add_callback_threadsafe(self.connection.close)
            except (OSError, pika.exceptions.AMQPError):
                pass
        if self.thread:
            self.thread.join(timeout=10)

    def _run(self) -> None:
        """Reconnect until stopped: a broker outage must not end the consumer."""
        while not self.stop_event.is_set():
            try:
                self._consume()
            except Exception:
                logger.exception(
                    "RabbitMQ consumer stopped unexpectedly for queue %s; retrying.",
                    self.queue_name,
                )
                self.stop_event.wait(RECONNECT_DELAY_SECONDS)

    def _consume(self) -> None:
        connection = consumer_connection()
        self.connection = connection
        channel = connection.channel()
        logger.info("RabbitMQ consumer connected to queue %s.", self.queue_name)
        on_message = self._declare(channel)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=self.queue_name, on_message_callback=on_message)
        channel.start_consuming()

    def _declare(self, channel) -> Callable:
        """Declare the queue for the configured mode and return its message callback."""
        if not self.use_retry_topology:
            declare_simple_topology(
                channel,
                self.queue_name,
                self.exchange or rabbitmq_exchange(),
                self.routing_keys,
            )
            return self._handle_simple
        topology = declare_consumer_topology(
            channel,
            self.queue_name,
            self.routing_keys,
            self.retry_delay_seconds,
        )
        return partial(self._handle_with_retry, topology)

    # --- Message handling ----------------------------------------------------

    def _receive(self, body: bytes, event_type: str) -> tuple[dict[str, Any], str]:
        """Decode the message and log its arrival. Raises json.JSONDecodeError."""
        event = json.loads(body)
        event_type = event.get("event_type", event_type)
        logger.info(
            "Received RabbitMQ event %s (%s) from queue %s.",
            event.get("event_id", "unknown"),
            event_type,
            self.queue_name,
        )
        return event, event_type

    def _handle_with_retry(self, topology: ConsumerTopology, ch, method, properties, body) -> None:
        """Retry topology: ack on success, otherwise route to retry or DLQ, then ack."""
        event_type = properties.type if properties else "unknown"
        attempt = delivery_attempt(properties) + 1
        try:
            event, event_type = self._receive(body, event_type)
            self.handler(event)
        except PermanentEventError:
            logger.exception("Permanent RabbitMQ event failure; sending %s to DLQ.", event_type)
            publish_dead_letter(ch, topology, body, properties, event_type)
        except Exception:
            logger.exception(
                "RabbitMQ event handling failed for %s (attempt %s/%s).",
                event_type,
                attempt,
                self.max_delivery_attempts,
            )
            if not self._route_failure(ch, topology, body, properties, event_type, attempt):
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return
        ch.basic_ack(delivery_tag=method.delivery_tag)

    def _route_failure(self, ch, topology, body, properties, event_type: str, attempt: int) -> bool:
        """Send a failed message to retry or, after the last attempt, to the DLQ.

        Returns False when the broker refused it; the caller then requeues.
        """
        try:
            if attempt >= self.max_delivery_attempts:
                publish_dead_letter(ch, topology, body, properties, event_type)
            else:
                publish_retry(
                    ch,
                    topology,
                    body,
                    properties,
                    event_type,
                    attempt,
                    self.retry_delay_seconds,
                )
        except Exception:
            logger.exception("Could not route failed RabbitMQ event %s; requeueing.", event_type)
            return False
        return True

    def _handle_simple(self, ch, method, properties, body) -> None:
        """Simple mode: ack on success, ack+log on permanent errors, delayed nack(requeue) otherwise."""
        event_type = properties.type if properties else "unknown"
        try:
            event, event_type = self._receive(body, event_type)
            self.handler(event)
        except (PermanentEventError, json.JSONDecodeError):
            logger.exception(
                "Permanent failure for %s in queue %s; message is dropped.",
                event_type,
                self.queue_name,
            )
        except Exception:
            logger.exception(
                "Handling %s from queue %s failed; requeueing in %ss.",
                event_type,
                self.queue_name,
                self.retry_delay_seconds,
            )
            ch.connection.sleep(self.retry_delay_seconds)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)
