"""Gemini adapter of LLMClient: request mapping, response parsing, errors (no real API calls)."""

import dataclasses
import asyncio
import logging
from types import SimpleNamespace

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import SecretStr

from shared.ai_tools.config import LLMSettings
from shared.ai_tools.llm import (
    LLMClient,
    LLMRateLimitError,
    LLMUnavailableError,
    ModelTurn,
    ToolCall,
    ToolResult,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from shared.ai_tools.llm.gemini import GeminiLLMClient

SECRET = "test-gemini-key-that-must-never-leak"


def _settings() -> LLMSettings:
    return LLMSettings(
        provider="gemini",
        api_key=SecretStr(SECRET),
        model="gemini-test-model",
        temperature=0.0,
        max_output_tokens=256,
        request_timeout_seconds=5.0,
    )


class FakeModels:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _fake_sdk(result) -> tuple[SimpleNamespace, FakeModels]:
    models = FakeModels(result)
    return SimpleNamespace(aio=SimpleNamespace(models=models)), models


def _response(parts, *, finish="STOP", usage=None) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=finish,
            )
        ],
        usage_metadata=usage
        or types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100,
            candidates_token_count=20,
            thoughts_token_count=5,
            total_token_count=125,
        ),
    )


TOOLS = [ToolSpec(name="find_budget_by_period", description="Find budget.", parameters={"type": "object"})]


def test_adapter_implements_llm_client_protocol():
    sdk, _ = _fake_sdk(_response([types.Part(text="ok")]))
    assert isinstance(GeminiLLMClient(_settings(), sdk_client=sdk), LLMClient)


def test_request_disables_sdk_function_calling_and_applies_limits():
    sdk, models = _fake_sdk(_response([types.Part(text="Готово")]))
    client = GeminiLLMClient(_settings(), sdk_client=sdk)

    asyncio.run(client.generate(system_prompt="SYSTEM", conversation=[UserMessage("Привіт")], tools=TOOLS))

    call = models.calls[0]
    config = call["config"]
    assert call["model"] == "gemini-test-model"
    assert config.automatic_function_calling.disable is True
    assert config.max_output_tokens == 256
    assert config.temperature == 0.0
    assert config.system_instruction == "SYSTEM"
    declaration = config.tools[0].function_declarations[0]
    assert declaration.name == "find_budget_by_period"
    assert declaration.parameters_json_schema == {"type": "object"}
    assert call["contents"][0].role == "user"
    assert call["contents"][0].parts[0].text == "Привіт"


def test_function_calls_and_usage_are_parsed():
    usage = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=300,
        tool_use_prompt_token_count=10,
        candidates_token_count=40,
        thoughts_token_count=60,
        total_token_count=410,
    )
    parts = [
        types.Part(text="internal reasoning", thought=True),
        types.Part(function_call=types.FunctionCall(id="c1", name="find_budget_by_period", args={"year": 2026, "month": 11})),
    ]
    sdk, _ = _fake_sdk(_response(parts, usage=usage))

    result = asyncio.run(
        GeminiLLMClient(_settings(), sdk_client=sdk).generate(
            system_prompt="S", conversation=[UserMessage("x")], tools=TOOLS
        )
    )

    assert result.text is None  # thought parts are never shown to the user
    assert result.tool_calls == [ToolCall(name="find_budget_by_period", arguments={"year": 2026, "month": 11}, call_id="c1")]
    assert result.usage.input_tokens == 310
    assert result.usage.output_tokens == 100
    assert result.usage.total_tokens == 410
    assert result.finish_reason == "STOP"


def test_history_keeps_model_turn_and_sends_tool_results_with_call_id():
    first = _response([types.Part(function_call=types.FunctionCall(id="c1", name="find_budget_by_period", args={}))])
    sdk, models = _fake_sdk(first)
    client = GeminiLLMClient(_settings(), sdk_client=sdk)
    model_reply = asyncio.run(client.generate(system_prompt="S", conversation=[UserMessage("x")], tools=TOOLS))

    call = model_reply.tool_calls[0]
    history = [
        UserMessage("x"),
        ModelTurn(model_reply),
        ToolResultsMessage([ToolResult(call=call, content={"found": True})]),
    ]
    models.result = _response([types.Part(text="Бюджет знайдено")])
    final = asyncio.run(client.generate(system_prompt="S", conversation=history, tools=TOOLS))

    contents = models.calls[1]["contents"]
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert contents[1] is model_reply.provider_turn  # original content (thought signatures) is reused
    response_part = contents[2].parts[0].function_response
    assert response_part.id == "c1"
    assert response_part.name == "find_budget_by_period"
    assert response_part.response == {"found": True}
    assert final.text == "Бюджет знайдено"


def test_max_tokens_finish_reason_marks_response_truncated():
    sdk, _ = _fake_sdk(_response([types.Part(text="Обрізана від")], finish="MAX_TOKENS"))
    result = asyncio.run(
        GeminiLLMClient(_settings(), sdk_client=sdk).generate(system_prompt="S", conversation=[UserMessage("x")], tools=[])
    )
    assert result.truncated is True


def test_rate_limit_is_translated_and_secret_is_not_logged(caplog):
    error = genai_errors.ClientError(429, {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota"}})
    sdk, _ = _fake_sdk(error)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(LLMRateLimitError) as raised:
        asyncio.run(
            GeminiLLMClient(_settings(), sdk_client=sdk).generate(system_prompt="S", conversation=[UserMessage("x")], tools=[])
        )

    assert SECRET not in str(raised.value)
    assert SECRET not in caplog.text
    assert "code=429" in caplog.text


def test_server_error_is_translated_to_unavailable():
    error = genai_errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "down"}})
    sdk, _ = _fake_sdk(error)

    with pytest.raises(LLMUnavailableError):
        asyncio.run(
            GeminiLLMClient(_settings(), sdk_client=sdk).generate(system_prompt="S", conversation=[UserMessage("x")], tools=[])
        )


def test_thinking_level_is_not_sent_by_default():
    sdk, models = _fake_sdk(_response([types.Part(text="Готово")]))
    asyncio.run(
        GeminiLLMClient(_settings(), sdk_client=sdk).generate(
            system_prompt="S", conversation=[UserMessage("x")], tools=[]
        )
    )
    assert models.calls[0]["config"].thinking_config is None


def test_thinking_level_is_passed_to_gemini():
    sdk, models = _fake_sdk(_response([types.Part(text="Готово")]))
    settings = dataclasses.replace(_settings(), thinking_level="MINIMAL")
    asyncio.run(
        GeminiLLMClient(settings, sdk_client=sdk).generate(
            system_prompt="S", conversation=[UserMessage("x")], tools=[]
        )
    )
    assert models.calls[0]["config"].thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
