"""Response contract for the state of a "create expense" SAGA."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SagaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    saga_id: uuid.UUID
    saga_type: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    status: str
    current_step: str
    started_at: datetime
    deadline_at: datetime
    finished_at: datetime | None
    failure_reason: str | None
    failure_details: str | None
    compensation_attempts: int
    last_error: str | None
