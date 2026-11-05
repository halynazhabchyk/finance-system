"""Shared event envelope contract."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


def new_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str | None = None,
    event_version: int = 1,
) -> dict[str, Any]:
    """Create the versioned envelope used by all RabbitMQ events."""
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "event_version": event_version,
        "event_type": event_type,
        "created_at": datetime.now().astimezone().isoformat(),
        **payload,
    }
