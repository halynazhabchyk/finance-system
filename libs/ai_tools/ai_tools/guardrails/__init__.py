"""Guardrails of function calling."""

from ai_tools.guardrails.data_marking import UNTRUSTED_DATA_KEY, guard_tool_result, mark_as_untrusted_data
from ai_tools.guardrails.errors import GuardrailViolation
from ai_tools.guardrails.injection import ensure_no_prompt_injection, find_injection_rules
from ai_tools.guardrails.markup import (
    ensure_no_active_content,
    find_active_content_rules,
    sanitize_model_answer,
)
from ai_tools.guardrails.limits import TokenBudget, check_user_message, truncate_tool_result

__all__ = [
    "GuardrailViolation",
    "TokenBudget",
    "UNTRUSTED_DATA_KEY",
    "check_user_message",
    "ensure_no_active_content",
    "ensure_no_prompt_injection",
    "find_active_content_rules",
    "find_injection_rules",
    "guard_tool_result",
    "mark_as_untrusted_data",
    "sanitize_model_answer",
    "truncate_tool_result",
]
