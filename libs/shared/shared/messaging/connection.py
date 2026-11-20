"""RabbitMQ connection creation and lifecycle helpers."""

from __future__ import annotations

import logging
from threading import local

import pika

from .config import rabbitmq_url

logger = logging.getLogger(__name__)
_publisher_state = local()


def publisher_connection() -> pika.BlockingConnection:
    connection = getattr(_publisher_state, "connection", None)
    if connection is None or connection.is_closed:
        parameters = pika.URLParameters(rabbitmq_url())
        parameters.connection_attempts = 3
        parameters.retry_delay = 2
        connection = pika.BlockingConnection(parameters)
        _publisher_state.connection = connection
    return connection


def consumer_connection() -> pika.BlockingConnection:
    parameters = pika.URLParameters(rabbitmq_url())
    parameters.connection_attempts = 3
    return pika.BlockingConnection(parameters)


def discard_publisher_connection() -> None:
    connection = getattr(_publisher_state, "connection", None)
    _publisher_state.connection = None
    if connection and connection.is_open:
        try:
            connection.close()
        except pika.exceptions.AMQPError:
            logger.debug("RabbitMQ publisher connection was already unavailable.")
