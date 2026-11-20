"""Client-side memory of one request."""

from __future__ import annotations

WAITING_STATES = {"INPUT_REQUIRED"}


class Conversation:
    def __init__(self) -> None:
        self._context: str | None = None

    @property
    def awaiting_answer(self) -> bool:
        return self._context is not None

    def compose(self, user_text: str) -> str:
        """The text to send: the new message, or the open request plus the answer."""
        if self._context is None:
            return user_text
        return f"{self._context}\nВідповідь: {user_text}"

    def record(self, sent_text: str, state: str, agent_message: str) -> None:
        if state in WAITING_STATES:
            question = agent_message.strip()
            self._context = f"{sent_text}\nУточнення агента: {question}" if question else sent_text
        else:
            self._context = None

    def reset(self) -> None:
        self._context = None
