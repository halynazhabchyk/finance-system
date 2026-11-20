"""RabbitMQ-specific exceptions."""


class RabbitMQError(RuntimeError):
    """Base error for RabbitMQ operations."""


class RabbitMQPublishError(RabbitMQError):
    """An event could not be published after retries."""


class PermanentEventError(RabbitMQError):
    """An event cannot be processed or retried."""
