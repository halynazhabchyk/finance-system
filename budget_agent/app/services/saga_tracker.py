"""Waits for the "CreateExpense" SAGA through GET .../expenses/{id}/saga.

SAGA states (ЛР №3): STARTED -> COMPLETED (expense CONFIRMED) or
STARTED -> COMPENSATING -> CANCELLED (expense CANCELLED, reason DLQ/TIMEOUT).
The agent only observes the SAGA; it never changes it.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.integrations.budget_api import BudgetAgentApiClient

logger = logging.getLogger(__name__)

FINAL_SAGA_STATES = {"COMPLETED", "CANCELLED"}


@dataclass(frozen=True)
class SagaOutcome:
    saga_id: str | None
    status: str
    failure_reason: str | None
    failure_details: str | None
    timed_out: bool

    @property
    def expense_status(self) -> str:
        return {"COMPLETED": "CONFIRMED", "CANCELLED": "CANCELLED"}.get(self.status, "PENDING")


async def wait_for_saga(
    api: BudgetAgentApiClient,
    budget_id: uuid.UUID,
    expense_id: uuid.UUID,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    on_progress: Callable[[str], Awaitable[None]] | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> SagaOutcome:
    deadline = time.monotonic() + timeout_seconds
    last_status: str | None = None
    saga: dict = {}
    while True:
        saga = await api.get_expense_saga(budget_id, expense_id)
        status = saga["status"]
        if status != last_status:
            logger.info("saga_observed expense_id=%s saga_id=%s status=%s", expense_id, saga.get("saga_id"), status)
            if on_progress is not None and status not in FINAL_SAGA_STATES:
                await on_progress(status)
            last_status = status
        if status in FINAL_SAGA_STATES:
            return SagaOutcome(saga.get("saga_id"), status, saga.get("failure_reason"), saga.get("failure_details"), False)
        if time.monotonic() >= deadline:
            return SagaOutcome(saga.get("saga_id"), status, None, None, True)
        await sleep(poll_interval_seconds)
