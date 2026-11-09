"""Test doubles shared by the test suites of the AI components.

* ``ScriptedLLMClient`` – an ``LLMClient`` that replays prepared responses
  (no real model calls in tests, requirement 6.2);
* ``FakeFinanceApi`` – an in-memory imitation of the public REST API behind
  Traefik, plugged into ``FinanceApiClient`` through ``httpx.MockTransport``.
"""

from shared.ai_tools.testing.fake_api import FakeFinanceApi, make_jwt
from shared.ai_tools.testing.scripted_llm import (
    ScriptedLLMClient,
    final_answer,
    latest_tool_result,
    tool_call_response,
)

__all__ = [
    "FakeFinanceApi",
    "ScriptedLLMClient",
    "final_answer",
    "latest_tool_result",
    "make_jwt",
    "tool_call_response",
]
