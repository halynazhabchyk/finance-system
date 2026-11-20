"""shared EventConsumer in retry-topology mode (used by ReportEventConsumer)."""

import json
from types import SimpleNamespace

import pytest

from shared.messaging import consumer as consumer_module
from shared.messaging.exceptions import PermanentEventError
from shared.messaging.topology import ConsumerTopology

TOPOLOGY = ConsumerTopology(
    exchange="finance.events",
    retry_exchange="finance.events.retry",
    dlq_exchange="finance.events.dlx",
    retry_queue="report-service-events.retry",
    dlq_name="report-service-events.dlq",
)


class FakeChannel:
    def __init__(self):
        self.acks = []
        self.nacks = []

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))


@pytest.fixture
def routed(monkeypatch):
    """Records where failed messages are sent instead of publishing them."""
    sent = []
    monkeypatch.setattr(
        consumer_module,
        "publish_retry",
        lambda ch, topology, body, props, key, attempt, delay: sent.append(("retry", key, attempt)),
    )
    monkeypatch.setattr(
        consumer_module,
        "publish_dead_letter",
        lambda ch, topology, body, props, key: sent.append(("dlq", key)),
    )
    return sent


def deliver(handler, *, attempt=0, body=None):
    consumer = consumer_module.EventConsumer(
        "report-service-events",
        ["ExpenseCreated"],
        handler,
        max_delivery_attempts=3,
        retry_delay_seconds=5,
    )
    channel = FakeChannel()
    properties = SimpleNamespace(type="ExpenseCreated", headers={"x-delivery-attempt": attempt})
    payload = body if body is not None else json.dumps({"event_id": "e1", "event_type": "ExpenseCreated"})
    consumer._handle_with_retry(TOPOLOGY, channel, SimpleNamespace(delivery_tag=7), properties, payload)
    return channel


def fail(event):
    raise RuntimeError("database is down")


def test_success_is_acknowledged(routed):
    handled = []

    channel = deliver(handled.append)

    assert [event["event_id"] for event in handled] == ["e1"]
    assert channel.acks == [7]
    assert routed == []


def test_failure_before_last_attempt_is_scheduled_for_retry(routed):
    channel = deliver(fail, attempt=1)

    assert routed == [("retry", "ExpenseCreated", 2)]
    assert channel.acks == [7]


def test_failure_on_last_attempt_goes_to_dlq(routed):
    channel = deliver(fail, attempt=2)

    assert routed == [("dlq", "ExpenseCreated")]
    assert channel.acks == [7]


def test_permanent_error_goes_to_dlq_without_retry(routed):
    def reject(event):
        raise PermanentEventError("unsupported")

    channel = deliver(reject)

    assert routed == [("dlq", "ExpenseCreated")]
    assert channel.acks == [7]


def test_message_is_requeued_when_broker_refuses_routing(monkeypatch):
    def broker_down(*args):
        raise OSError("connection lost")

    monkeypatch.setattr(consumer_module, "publish_retry", broker_down)

    channel = deliver(fail)

    assert channel.acks == []
    assert channel.nacks == [(7, True)]


def test_invalid_json_is_retried_like_other_failures(routed):
    channel = deliver(lambda event: None, body=b"not json")

    assert routed == [("retry", "ExpenseCreated", 1)]
    assert channel.acks == [7]
