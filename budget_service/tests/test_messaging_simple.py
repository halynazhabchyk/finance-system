import json
from types import SimpleNamespace

import pytest


class FakeChannel:
    def __init__(self):
        self.acks = []
        self.nacks = []
        self.slept = []
        self.connection = SimpleNamespace(sleep=self.slept.append)

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))


def _consumer(handler):
    from shared.messaging.consumer import EventConsumer

    return EventConsumer(
        queue_name="budget-service-saga-events",
        routing_keys=["ExpenseProcessed"],
        handler=handler,
        retry_delay_seconds=2,
        use_retry_topology=False,
    )


def _deliver(consumer, payload):
    channel = FakeChannel()
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    consumer._handle_simple(
        channel,
        SimpleNamespace(delivery_tag=7),
        SimpleNamespace(type="ExpenseProcessed", headers={}),
        body,
    )
    return channel


def test_simple_mode_acks_after_successful_handler():
    handled = []
    channel = _deliver(_consumer(handled.append), {"event_id": "1", "event_type": "ExpenseProcessed"})

    assert handled and channel.acks == [7] and channel.nacks == []


def test_simple_mode_requeues_transient_failures_after_delay():
    def fail(event):
        raise RuntimeError("database is down")

    channel = _deliver(_consumer(fail), {"event_id": "1", "event_type": "ExpenseProcessed"})

    assert channel.slept == [2]
    assert channel.nacks == [(7, True)]
    assert channel.acks == []


@pytest.mark.parametrize("body", [b"not json", {"event_id": "1"}])
def test_simple_mode_drops_permanent_failures(body):
    from shared.messaging.exceptions import PermanentEventError

    def reject(event):
        raise PermanentEventError("malformed")

    channel = _deliver(_consumer(reject), body)

    assert channel.acks == [7]
    assert channel.nacks == []
