"""Readiness of the Scheduler: RabbitMQ connected and jobs scheduled."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Readiness:
    rabbitmq_available: bool = False
    scheduler_running: bool = False

    @property
    def ready(self) -> bool:
        return self.rabbitmq_available and self.scheduler_running
