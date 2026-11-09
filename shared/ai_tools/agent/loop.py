"""The function-calling loop: model -> tool calls -> results -> model ... -> final answer.

The loop stops when the model answers without tool calls, or when a limit is
reached (iterations, token budget). Limits are checked before every further
model call, so an exhausted budget never triggers another paid request.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Literal

from shared.ai_tools.config import AgentLimits
from shared.ai_tools.guardrails.data_marking import guard_tool_result
from shared.ai_tools.guardrails.limits import TokenBudget
from shared.ai_tools.guardrails.markup import sanitize_model_answer
from shared.ai_tools.llm.client import (
    ConversationItem,
    LLMClient,
    ModelTurn,
    TokenUsage,
    ToolResult,
    ToolResultsMessage,
    UserMessage,
)
from shared.ai_tools.tools.executor import ToolExecution, ToolExecutor

logger = logging.getLogger(__name__)

StopReason = Literal["completed", "max_iterations", "token_budget_exceeded", "output_truncated"]

STOP_MESSAGES: dict[str, str] = {
    "max_iterations": (
        "Запит зупинено: досягнуто ліміту кроків ({limit}) виклику інструментів. "
        "Сформулюйте запит простіше або розбийте його на кілька окремих."
    ),
    "token_budget_exceeded": (
        "Запит зупинено: вичерпано ліміт токенів на запит ({used} із {limit}). "
        "Сформулюйте запит коротше або розбийте його на частини."
    ),
    "output_truncated": (
        "Відповідь моделі обірвалася через ліміт вихідних токенів. Спробуйте поставити коротше питання."
    ),
}


@dataclass(frozen=True)
class AgentRunResult:
    answer: str
    tool_calls: list[ToolExecution]
    usage: TokenUsage
    stopped_reason: StopReason
    iterations: int
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class FunctionCallingLoop:
    """One configured agent: model, system prompt, tool executor and limits."""

    def __init__(
        self,
        *,
        llm: LLMClient,
        executor: ToolExecutor,
        system_prompt: str,
        limits: AgentLimits,
    ) -> None:
        self._llm = llm
        self._executor = executor
        self._system_prompt = system_prompt
        self._limits = limits

    async def run(self, user_message: str, *, request_id: str | None = None) -> AgentRunResult:
        request_id = request_id or uuid.uuid4().hex[:12]
        conversation: list[ConversationItem] = [UserMessage(user_message)]
        budget = TokenBudget(limit=self._limits.max_tokens_per_request)
        executions: list[ToolExecution] = []
        tools = self._executor.tool_specs()

        for iteration in range(1, self._limits.max_tool_iterations + 1):
            response = await self._llm.generate(
                system_prompt=self._system_prompt,
                conversation=conversation,
                tools=tools,
            )
            budget.add(response.usage)
            logger.info(
                "llm_usage request_id=%s iteration=%d input_tokens=%d output_tokens=%d "
                "total_tokens=%d cumulative_tokens=%d limit=%d tool_calls=%d",
                request_id,
                iteration,
                response.usage.input_tokens,
                response.usage.output_tokens,
                response.usage.total_tokens,
                budget.used.total_tokens,
                budget.limit,
                len(response.tool_calls),
            )

            if not response.tool_calls:
                if response.truncated and not response.text:
                    return self._stop("output_truncated", executions, budget, iteration, request_id)
                answer = response.text or ""
                if response.truncated:
                    answer = f"{answer}\n\n{STOP_MESSAGES['output_truncated']}"
                return self._result(answer, "completed", executions, budget, iteration, request_id)

            if budget.exceeded:
                return self._stop("token_budget_exceeded", executions, budget, iteration, request_id)

            conversation.append(ModelTurn(response))
            results: list[ToolResult] = []
            for call in response.tool_calls:  # sequential: later calls may depend on earlier ones
                execution = await self._executor.execute(call)
                executions.append(execution)
                # Every result is size-limited and marked as untrusted data before the model sees it.
                guarded = guard_tool_result(execution.result, self._limits.tool_result_max_chars)
                results.append(ToolResult(call=call, content=guarded))
            conversation.append(ToolResultsMessage(results))

        return self._stop(
            "max_iterations", executions, budget, self._limits.max_tool_iterations, request_id
        )

    def _stop(
        self,
        reason: StopReason,
        executions: list[ToolExecution],
        budget: TokenBudget,
        iterations: int,
        request_id: str,
    ) -> AgentRunResult:
        logger.warning(
            "agent_stopped request_id=%s reason=%s iterations=%d cumulative_tokens=%d",
            request_id,
            reason,
            iterations,
            budget.used.total_tokens,
        )
        message = STOP_MESSAGES[reason].format(
            limit=budget.limit if reason == "token_budget_exceeded" else self._limits.max_tool_iterations,
            used=budget.used.total_tokens,
        )
        return self._result(message, reason, executions, budget, iterations, request_id)

    @staticmethod
    def _result(
        answer: str,
        reason: StopReason,
        executions: list[ToolExecution],
        budget: TokenBudget,
        iterations: int,
        request_id: str,
    ) -> AgentRunResult:
        # The answer may be rendered by a client: no markup, external images or script links.
        answer, removed = sanitize_model_answer(answer)
        if removed:
            logger.warning("model_answer_sanitized request_id=%s removed=%s", request_id, ",".join(removed))
        return AgentRunResult(
            answer=answer,
            tool_calls=executions,
            usage=budget.used,
            stopped_reason=reason,
            iterations=iterations,
            request_id=request_id,
        )
