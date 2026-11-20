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
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    aggregate_version: int | None = None,
) -> dict[str, Any]:
    """Create the versioned envelope used by all RabbitMQ events."""
    event = {
        "event_id": event_id or str(uuid.uuid4()),
        "event_version": event_version,
        "event_type": event_type,
        "created_at": datetime.now().astimezone().isoformat(),
        **payload,
    }
    if aggregate_type is not None:
        event["aggregate_type"] = aggregate_type
    if aggregate_id is not None:
        event["aggregate_id"] = aggregate_id
    if aggregate_version is not None:
        event["aggregate_version"] = aggregate_version
    return event
