"""Contracts of ``POST /api/assistant/chat``."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Hard transport limit; the configurable limit (USER_MESSAGE_MAX_CHARS) is a guardrail in the service.
MAX_REQUEST_MESSAGE_CHARS = 20000


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=MAX_REQUEST_MESSAGE_CHARS,
        examples=["Скільки я ще можу витратити на розваги в листопаді 2026?"],
    )


class ToolCallInfo(BaseModel):
    name: str
    arguments: dict[str, Any]
    status: Literal["ok", "rejected", "invalid_arguments", "error"]
    duration_ms: int


class TokenUsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    tool_calls: list[ToolCallInfo]
    usage: TokenUsageInfo
    stopped_reason: Literal["completed", "max_iterations", "token_budget_exceeded", "output_truncated"]
