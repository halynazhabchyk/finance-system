"""Backward-compatible RabbitMQ transport facade.

Use the focused modules for new code:
config, exceptions, connection, topology, publisher, retry, and consumer.
"""

from .consumer import EventConsumer
from .config import rabbitmq_url
from .exceptions import PermanentEventError, RabbitMQError, RabbitMQPublishError
from .publisher import publish_event

__all__ = [
    "EventConsumer",
    "PermanentEventError",
    "RabbitMQError",
    "RabbitMQPublishError",
    "publish_event",
    "rabbitmq_url",
]
