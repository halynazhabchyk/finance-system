"""``SkillContext`` – what a skill handler gets: the request, an API client with the
user's JWT and the controls of the A2A task (state changes are logged with task_id)."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from a2a.helpers.proto_helpers import new_data_part, new_text_part
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from shared.ai_tools.a2a.requests import SkillRequest
from shared.ai_tools.gateway import FinanceApiClient

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """What a skill handler gets: the request, an API client with the user's JWT, and task controls."""

    agent_name: str
    task_id: str
    request: SkillRequest
    access_token: str
    api: FinanceApiClient
    _updater: TaskUpdater

    async def working(self, text: str) -> None:
        await self._status(TaskState.TASK_STATE_WORKING, text)

    async def artifact(self, name: str, data: dict[str, Any]) -> None:
        await self._updater.add_artifact([new_data_part(_json_safe(data))], name=name)
        logger.info("a2a_artifact agent=%s task_id=%s name=%s", self.agent_name, self.task_id, name)

    async def complete(self, text: str) -> None:
        await self._status(TaskState.TASK_STATE_COMPLETED, text)

    async def fail(self, text: str) -> None:
        await self._status(TaskState.TASK_STATE_FAILED, text)

    async def reject(self, text: str) -> None:
        await self._status(TaskState.TASK_STATE_REJECTED, text)

    async def require_input(self, text: str) -> None:
        await self._status(TaskState.TASK_STATE_INPUT_REQUIRED, text)

    async def _status(self, state: TaskState, text: str) -> None:
        logger.info(
            "a2a_task_state agent=%s task_id=%s state=%s detail=%s",
            self.agent_name,
            self.task_id,
            TaskState.Name(state).removeprefix("TASK_STATE_"),
            text[:160].replace("\n", " "),
        )
        await self._updater.update_status(state, self._updater.new_agent_message([new_text_part(text)]))


SkillHandler = Callable[[SkillContext], Awaitable[None]]


def _json_safe(data: dict[str, Any]) -> dict[str, Any]:
    """Data parts are protobuf Values: Decimal/UUID/date must become JSON primitives."""
    return json.loads(json.dumps(data, default=str))
