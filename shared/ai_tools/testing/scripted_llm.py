"""``LLMClient`` that replays a script of responses and records every request."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from shared.ai_tools.llm.client import (
    ConversationItem,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
)

Step = LLMResponse | Callable[[Sequence[ConversationItem]], LLMResponse] | Exception


def tool_call_response(*calls: tuple[str, dict[str, Any]], tokens: int = 100) -> LLMResponse:
    return LLMResponse(
        text=None,
        tool_calls=[ToolCall(name=name, arguments=arguments, call_id=f"call-{index}") for index, (name, arguments) in enumerate(calls)],
        usage=TokenUsage(input_tokens=tokens - 10, output_tokens=10, total_tokens=tokens),
        finish_reason="STOP",
    )


def final_answer(text: str, tokens: int = 100, finish_reason: str = "STOP") -> LLMResponse:
    return LLMResponse(
        text=text,
        usage=TokenUsage(input_tokens=tokens - 10, output_tokens=10, total_tokens=tokens),
        finish_reason=finish_reason,
    )


@dataclass
class RecordedRequest:
    system_prompt: str
    conversation: list[ConversationItem]
    tools: list[ToolSpec]


class ScriptedLLMClient:
    def __init__(self, steps: Sequence[Step]) -> None:
        self._steps = list(steps)
        self.requests: list[RecordedRequest] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        conversation: Sequence[ConversationItem],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        self.requests.append(RecordedRequest(system_prompt, list(conversation), list(tools)))
        if not self._steps:
            raise AssertionError("The scripted LLM received more requests than scripted steps.")
        step = self._steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step(conversation) if callable(step) else step

    def last_tool_envelopes(self) -> list[dict[str, Any]]:
        """Tool results exactly as the model received them in its latest request (with the data envelope)."""
        for item in reversed(self.requests[-1].conversation):
            if isinstance(item, ToolResultsMessage):
                return [result.content for result in item.results]
        return []

    def last_tool_results(self) -> list[dict[str, Any]]:
        """Payloads of the latest tool results (inside the ``untrusted_data`` envelope)."""
        return [unwrap(envelope) for envelope in self.last_tool_envelopes()]


def unwrap(envelope: dict[str, Any]) -> dict[str, Any]:
    return envelope.get("untrusted_data", envelope)


def latest_tool_result(conversation: Sequence[ConversationItem]) -> dict[str, Any]:
    """Payload of the first result in the latest tool message (for steps that react to results)."""
    message = next(item for item in reversed(conversation) if isinstance(item, ToolResultsMessage))
    return unwrap(message.results[0].content)
