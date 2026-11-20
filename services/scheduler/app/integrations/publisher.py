"""Async adapter over shared.messaging (pika) for the APScheduler jobs.

publish_event is blocking and keeps its RabbitMQ connection per thread, so every call
runs in one dedicated thread: the connection is reused and the event loop is not blocked.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pika

from shared.messaging import RabbitMQError, RabbitMQPublishError, publish_event
from shared.messaging.connection import discard_publisher_connection, publisher_connection


class EventPublisher:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rabbitmq-publisher")
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def connect(self) -> None:
        try:
            connection = await self._run(publisher_connection)
        except (OSError, pika.exceptions.AMQPError) as error:
            self._available = False
            raise RabbitMQError("Could not connect to RabbitMQ.") from error
        self._available = connection.is_open

    async def publish(self, event: dict[str, Any]) -> None:
        """Publisher confirms and retries come from shared.messaging."""
        try:
            await self._run(publish_event, event)
        except RabbitMQPublishError:
            self._available = False
            raise
        self._available = True

    async def close(self) -> None:
        await self._run(discard_publisher_connection)
        self._executor.shutdown(wait=False)
        self._available = False

    async def _run(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(self._executor, function, *args)
