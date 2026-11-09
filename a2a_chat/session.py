"""One chat session with an agent: commands and A2A messages."""

from __future__ import annotations

from shared.ai_tools.a2a.client import RemoteAgentClient, RemoteAgentError

from a2a_chat.config import AgentTarget
from a2a_chat.console import HELP, Console
from a2a_chat.conversation import Conversation

EXIT_COMMANDS = {"вихід", "exit", "quit"}
CARD_COMMANDS = {"картка", "card"}
NEW_COMMANDS = {"новий", "new"}
HELP_COMMANDS = {"допомога", "help", "?"}


class ChatSession:
    def __init__(self, *, remote: RemoteAgentClient, target: AgentTarget, console: Console) -> None:
        self._remote = remote
        self._target = target
        self._console = console
        self._conversation = Conversation()

    @property
    def awaiting_answer(self) -> bool:
        return self._conversation.awaiting_answer

    async def start(self) -> None:
        """Discover the agent: the card must declare the text skill and JWT authentication."""
        card = await self._remote.discover(self._target.text_skill)
        self._console.card(card)
        self._console.info(self._target.hint)
        self._console.info(HELP)

    async def handle(self, line: str) -> bool:
        """Process one input line; ``False`` ends the session."""
        text = line.strip()
        command = text.lower()
        if not text:
            return True
        if command in EXIT_COMMANDS:
            return False
        if command in HELP_COMMANDS:
            self._console.info(HELP)
            return True
        if command in CARD_COMMANDS:
            if self._remote.card is not None:
                self._console.card(self._remote.card)
            return True
        if command in NEW_COMMANDS:
            self._conversation.reset()
            self._console.info("Новий запит: попередні уточнення забуто.")
            return True
        await self._send(text)
        return True

    async def _send(self, text: str) -> None:
        message = self._conversation.compose(text)
        try:
            result = await self._remote.run_text(message, on_state=self._console.state)
        except RemoteAgentError as error:
            self._conversation.reset()
            self._console.error(str(error))
            return
        self._console.result(result)
        self._conversation.record(message, result.state, result.message)
        if self._conversation.awaiting_answer:
            self._console.info("Агент чекає уточнення: відповідайте наступним повідомленням (або «новий»).")
