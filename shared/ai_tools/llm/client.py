"""The ``LLMClient`` abstraction and the neutral conversation types.S"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolSpec:
    """What the model is told about one tool: name, when to use it, JSON schema of arguments."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asks to run tool ``name`` with ``arguments``."""

    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass(frozen=True)
class TokenUsage:
    """Tokens reported by the provider for one or several model calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass(frozen=True)
class LLMResponse:
    """One answer of the model: final text and/or tool calls.

    ``provider_turn`` is the provider's own representation of the model
    message. The adapter puts it back into the history unchanged (Gemini
    requires e.g. ``thought_signature`` to survive between calls); other code
    must treat it as opaque.
    """

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None
    provider_turn: Any = None

    @property
    def truncated(self) -> bool:
        """The provider stopped because the output-token limit was reached."""
        return (self.finish_reason or "").upper() == "MAX_TOKENS"


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class ModelTurn:
    response: LLMResponse


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    content: dict[str, Any]


@dataclass(frozen=True)
class ToolResultsMessage:
    results: list[ToolResult]


ConversationItem = UserMessage | ModelTurn | ToolResultsMessage


@runtime_checkable
class LLMClient(Protocol):
    """A language model with function calling."""

    async def generate(
        self,
        *,
        system_prompt: str,
        conversation: Sequence[ConversationItem],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        
        ...
