"""RabbitMQ exchange, queue and binding declarations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pika

from .config import rabbitmq_exchange


@dataclass(frozen=True)
class ConsumerTopology:
    exchange: str
    retry_exchange: str
    dlq_exchange: str
    retry_queue: str
    dlq_name: str


def declare_consumer_topology(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    queue_name: str,
    routing_keys: list[str],
    retry_delay: int,
) -> ConsumerTopology:
    exchange = rabbitmq_exchange()
    topology = ConsumerTopology(
        exchange=exchange,
        retry_exchange=f"{exchange}.retry",
        dlq_exchange=f"{exchange}.dlx",
        retry_queue=f"{queue_name}.retry",
        dlq_name=f"{queue_name}.dlq",
    )

    for name in (
        topology.exchange,
        topology.retry_exchange,
        topology.dlq_exchange,
    ):
        channel.exchange_declare(
            exchange=name,
            exchange_type="topic",
            durable=True,
        )

    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_declare(
        queue=topology.retry_queue,
        durable=True,
        arguments={
            "x-message-ttl": retry_delay * 1000,
            "x-dead-letter-exchange": topology.exchange,
        },
    )
    channel.queue_bind(
        exchange=topology.retry_exchange,
        queue=topology.retry_queue,
        routing_key="#",
    )
    channel.queue_declare(queue=topology.dlq_name, durable=True)
    channel.queue_bind(
        exchange=topology.dlq_exchange,
        queue=topology.dlq_name,
        routing_key="#",
    )
    for routing_key in routing_keys:
        channel.queue_bind(
            exchange=topology.exchange,
            queue=queue_name,
            routing_key=routing_key,
        )
    return topology


def declare_simple_topology(
    channel: pika.adapters.blocking_connection.BlockingChannel,
    queue_name: str,
    exchange: str,
    routing_keys: list[str],
) -> None:
    """Durable queue bound to one topic exchange, without retry/DLQ bindings.

    Used by consumers whose failures are retried with nack/requeue, so they do
    not add more "#" bindings to the shared retry and dead-letter exchanges.
    """
    channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
    channel.queue_declare(queue=queue_name, durable=True)
    for routing_key in routing_keys:
        channel.queue_bind(exchange=exchange, queue=queue_name, routing_key=routing_key)
