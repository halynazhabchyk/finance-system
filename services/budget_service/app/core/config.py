"""Settings of Budget Service: read once from environment variables and validated at startup."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from shared.db import DatabaseSettings

SERVICE_ROOT = Path(__file__).resolve().parents[2]
TRUE_VALUES = {"1", "true", "yes"}


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    public_api_prefix: str
    database: DatabaseSettings
    instance_id: str
    outbox_poll_interval: float
    outbox_simulate_failure: bool
    saga_timeout_seconds: int
    saga_watch_interval: float

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(SERVICE_ROOT / ".env")
        return cls(
            public_api_prefix=os.getenv("PUBLIC_API_PREFIX", ""),
            database=DatabaseSettings.from_env("BUDGET"),
            instance_id=os.getenv("HOSTNAME") or socket.gethostname(),
            outbox_poll_interval=float(os.getenv("OUTBOX_POLL_INTERVAL", "2")),
            outbox_simulate_failure=_flag("OUTBOX_SIMULATE_FAILURE"),
            saga_timeout_seconds=max(1, int(os.getenv("SAGA_TIMEOUT_SECONDS", "30"))),
            saga_watch_interval=float(os.getenv("SAGA_WATCH_INTERVAL", "5")),
        )


@lru_cache
def get_settings() -> Settings:
    """One instance per process; tests call get_settings.cache_clear() after changing the environment."""
    return Settings.from_env()
