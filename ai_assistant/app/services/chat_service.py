"""Use case "chat with the assistant" – independent of FastAPI.

Order of checks for one request:
1. size of the message, the prompt-injection and active-content filters (no tokens spent);
2. the JWT through User Service (an invalid or blocked user spends no tokens);
3. the function-calling loop with the five whitelisted tools.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from shared.ai_tools.agent import AgentRunResult, FunctionCallingLoop
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.gateway.factory import ApiClientFactory
from shared.ai_tools.guardrails import (
    check_user_message,
    ensure_no_active_content,
    ensure_no_prompt_injection,
)
from shared.ai_tools.llm import LLMClient
from shared.ai_tools.tools import ToolExecutor

from app.core.prompts import build_system_prompt

logger = logging.getLogger(__name__)


class AssistantChatService:
    def __init__(
        self,
        *,
        llm: LLMClient,
        limits: AgentLimits,
        api_client_factory: ApiClientFactory,
        today: Callable[[], date] = date.today,
    ) -> None:
        self._llm = llm
        self._limits = limits
        self._api_client_factory = api_client_factory
        self._today = today

    async def chat(self, message: str, access_token: str) -> AgentRunResult:
        text = check_user_message(message, self._limits.user_message_max_chars)
        ensure_no_prompt_injection(text, source="assistant_chat")
        ensure_no_active_content(text, source="assistant_chat")
        async with self._api_client_factory(access_token) as client:
            user_id = await client.verify_current_user()
            loop = FunctionCallingLoop(
                llm=self._llm,
                executor=ToolExecutor(client),
                system_prompt=build_system_prompt(self._today().year),
                limits=self._limits,
            )
            result = await loop.run(text)
        logger.info(
            "assistant_chat request_id=%s user_id=%s stopped_reason=%s tool_calls=%d total_tokens=%d",
            result.request_id,
            user_id,
            result.stopped_reason,
            len(result.tool_calls),
            result.usage.total_tokens,
        )
        return result

