"""Outcome of a task run on a remote agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


class RemoteAgentError(Exception):
    """The remote agent could not be discovered or called."""


@dataclass
class RemoteTaskResult:
    task_id: str | None = None
    state: str = "UNSPECIFIED"
    message: str = ""
    states: list[str] = field(default_factory=list)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.state == "COMPLETED"


StateListener = Callable[[str, str], Awaitable[None]]
