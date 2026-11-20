"""RabbitMQ publisher for report update events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.config import SchedulerConfig

logger = logging.getLogger(__name__)


class EventPublisher:
    def __init__(self, config: SchedulerConfig):
        self._config = config
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    @property
    def available(self) -> bool:
        return bool(
            self._connection
            and not self._connection.is_closed
            and self._channel
            and not self._channel.is_closed
        )

    async def connect(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self._config.rabbitmq_publish_retries + 1):
            try:
                self._connection = await aio_pika.connect_robust(
                    self._config.rabbitmq_url
                )
                self._channel = await self._connection.channel()
                self._exchange = await self._channel.declare_exchange(
                    self._config.rabbitmq_exchange,
                    ExchangeType.TOPIC,
                    durable=True,
                )
                return
            except Exception as error:
                last_error = error
                logger.exception(
                    "RabbitMQ connection attempt %s/%s failed.",
                    attempt,
                    self._config.rabbitmq_publish_retries,
                )
                await asyncio.sleep(min(attempt, 5))
        raise RuntimeError("Could not connect to RabbitMQ.") from last_error

    async def publish(self, event: dict[str, Any]) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self._config.rabbitmq_publish_retries + 1):
            try:
                if not self.available:
                    await self.connect()
                assert self._exchange is not None
                await self._exchange.publish(
                    Message(
                        json.dumps(event).encode(),
                        content_type="application/json",
                        delivery_mode=DeliveryMode.PERSISTENT,
                        message_id=event["event_id"],
                        type=event["event_type"],
                    ),
                    routing_key=event["event_type"],
                )
                return
            except Exception as error:
                last_error = error
                logger.exception(
                    "RabbitMQ publish attempt %s/%s failed.",
                    attempt,
                    self._config.rabbitmq_publish_retries,
                )
                await asyncio.sleep(min(attempt, 5))
        raise RuntimeError("Could not publish report update event.") from last_error

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
