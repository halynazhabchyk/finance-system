"""Text output of the client: Agent Card, live task states, artifacts, errors."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from a2a.types import AgentCard

from shared.ai_tools.a2a.client import RemoteTaskResult

Writer = Callable[[str], None]

FINAL_STATES = {"COMPLETED", "FAILED", "REJECTED", "CANCELED", "INPUT_REQUIRED", "AUTH_REQUIRED"}

HELP = (
    "Команди: «картка» – Agent Card агента; «новий» – почати новий запит; "
    "«допомога» – ця підказка; «вихід» – завершити."
)


class Console:
    def __init__(self, write: Writer = print) -> None:
        self._write = write

    def line(self, text: str = "") -> None:
        self._write(text)

    def info(self, text: str) -> None:
        self._write(f"[i] {text}")

    def error(self, text: str) -> None:
        self._write(f"[помилка] {text}")

    def card(self, card: AgentCard) -> None:
        url = card.supported_interfaces[0].url if card.supported_interfaces else ""
        self._write(f"Agent Card: {card.name} {card.version} ({url})")
        self._write(f"  {card.description}")
        self._write("  Навички:")
        for skill in card.skills:
            modes = ", ".join(skill.input_modes) or "default"
            self._write(f"    - {skill.id}: {skill.name} [вхід: {modes}]")
        schemes = ", ".join(card.security_schemes) or "немає"
        self._write(f"  Автентифікація: {schemes}; потоковий режим: {card.capabilities.streaming}")

    async def state(self, state: str, text: str) -> None:
        """Called by RemoteAgentClient for every state update (streaming)."""
        if state in FINAL_STATES:
            return  # the final state is printed by ``result`` together with artifacts
        self._status(state, text)

    def result(self, result: RemoteTaskResult) -> None:
        self._status(result.state, result.message)
        for name, data in result.artifacts.items():
            self._write(f"  Артефакт «{name}»:")
            for line in _format(data).splitlines():
                self._write(f"    {line}")
        if result.task_id:
            self._write(f"  task_id: {result.task_id}; стани: {' -> '.join(result.states)}")

    def _status(self, state: str, text: str) -> None:
        """``  [STATE] text``; further lines of a multi-line message are indented under the text."""
        prefix = f"  [{state}] "
        lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()] or [""]
        self._write((prefix + lines[0]).rstrip())
        for line in lines[1:]:
            self._write(" " * len(prefix) + line)


def _format(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)
