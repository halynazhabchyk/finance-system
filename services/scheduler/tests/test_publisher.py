"""EventPublisher: async adapter over shared.messaging, one dedicated thread."""

import asyncio
import threading

import pika
import pytest

from app.integrations import publisher as module
from app.integrations.publisher import EventPublisher
from shared.messaging import RabbitMQError, RabbitMQPublishError


class FakeConnection:
    is_open = True


def test_publish_delegates_to_shared_in_one_dedicated_thread(monkeypatch):
    threads = []

    def publish_event(event):
        threads.append(threading.current_thread().name)

    monkeypatch.setattr(module, "publish_event", publish_event)
    publisher = EventPublisher()

    async def scenario():
        await publisher.publish({"event_id": "1", "event_type": "DailyReportUpdateRequested"})
        await publisher.publish({"event_id": "2", "event_type": "DailyReportUpdateRequested"})
        await publisher.close()

    monkeypatch.setattr(module, "discard_publisher_connection", lambda: None)
    asyncio.run(scenario())

    assert len(threads) == 2
    assert threads[0] == threads[1]  # the per-thread pika connection is reused
    assert threads[0].startswith("rabbitmq-publisher")
    assert threads[0] != threading.main_thread().name


def test_publish_failure_marks_unavailable_and_propagates(monkeypatch):
    def publish_event(event):
        raise RabbitMQPublishError("broker down")

    monkeypatch.setattr(module, "publish_event", publish_event)
    publisher = EventPublisher()

    with pytest.raises(RabbitMQPublishError):
        asyncio.run(publisher.publish({"event_id": "1", "event_type": "DailyReportUpdateRequested"}))
    assert publisher.available is False


def test_connect_sets_available(monkeypatch):
    monkeypatch.setattr(module, "publisher_connection", lambda: FakeConnection())
    publisher = EventPublisher()

    asyncio.run(publisher.connect())

    assert publisher.available is True


def test_connect_failure_raises_rabbitmq_error(monkeypatch):
    def refuse():
        raise pika.exceptions.AMQPConnectionError("refused")

    monkeypatch.setattr(module, "publisher_connection", refuse)
    publisher = EventPublisher()

    with pytest.raises(RabbitMQError):
        asyncio.run(publisher.connect())
    assert publisher.available is False
