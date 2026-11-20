"""Expected failure of a skill handler."""

from __future__ import annotations

from typing import Any


class SkillFailed(Exception):
    """Expected failure of a skill: the task becomes FAILED with this message (and optional data)."""

    def __init__(self, message: str, data: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.data = data
