"""Guardrails of level 1: token budget, iterations, sizes of messages and tool results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from shared.ai_tools.guardrails.errors import GuardrailViolation
from shared.ai_tools.llm.client import TokenUsage


@dataclass
class TokenBudget:
    """Cumulative token usage of one user request, measured from the provider ``usage``."""

    limit: int
    used: TokenUsage = field(default_factory=TokenUsage)

    def add(self, usage: TokenUsage) -> None:
        self.used = self.used + usage

    @property
    def exceeded(self) -> bool:
        return self.used.total_tokens >= self.limit

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used.total_tokens, 0)


def check_user_message(text: str, max_chars: int) -> str:
    """Reject empty or too long messages before they reach the model."""
    stripped = text.strip()
    if not stripped:
        raise GuardrailViolation("empty_message", "Повідомлення порожнє.")
    if len(stripped) > max_chars:
        raise GuardrailViolation(
            "message_too_long",
            f"Повідомлення задовге: {len(stripped)} символів, дозволено не більше {max_chars}.",
        )
    return stripped


def truncate_tool_result(result: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Keep the serialized tool result within ``max_chars`` (long lists are cut, flagged for the model)."""
    serialized = json.dumps(result, ensure_ascii=False, default=str)
    if len(serialized) <= max_chars:
        return result
    return {
        "truncated": True,
        "notice": f"The result was {len(serialized)} characters and was cut to {max_chars}. "
        "Ask the user to narrow the question if data is missing.",
        "partial_content": serialized[:max_chars],
    }
