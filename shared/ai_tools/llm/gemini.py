"""Google Gemini adapter of ``LLMClient`` (library ``google-genai``).

This is the only module of the project that imports ``google.genai``.
Automatic function calling of the SDK is disabled: tools are executed by our
own loop, which applies whitelisting, validation and token limits.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from shared.ai_tools.config import LLMSettings
from shared.ai_tools.llm.client import (
    ConversationItem,
    LLMResponse,
    ModelTurn,
    TokenUsage,
    ToolCall,
    ToolResultsMessage,
    ToolSpec,
    UserMessage,
)
from shared.ai_tools.llm.errors import LLMError, LLMRateLimitError, LLMUnavailableError

logger = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429


class GeminiLLMClient:
    """``LLMClient`` backed by the Gemini API."""

    def __init__(self, settings: LLMSettings, *, sdk_client: Any | None = None) -> None:
        self._settings = settings
        self._client = sdk_client or genai.Client(
            api_key=settings.api_key.get_secret_value(),
            http_options=types.HttpOptions(
                timeout=int(settings.request_timeout_seconds * 1000),
            ),
        )
    async def generate(
        self,
        *,
        system_prompt: str,
        conversation: Sequence[ConversationItem],
        tools: Sequence[ToolSpec],
    ) -> LLMResponse:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            tools=[_to_gemini_tool(tools)] if tools else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=_thinking_config(self._settings.thinking_level),
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._settings.model,
                contents=to_gemini_contents(conversation),
                config=config,
            )
        except genai_errors.APIError as error:
            raise _translate_api_error(error) from error
        except (httpx.TimeoutException, httpx.TransportError) as error:
            raise LLMUnavailableError("The language model did not respond in time.") from error
        return from_gemini_response(response)


def _thinking_config(level: str | None) -> types.ThinkingConfig | None:
    """Limit hidden reasoning; ``None`` leaves the model default unchanged."""
    if level is None:
        return None
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel(level))


def _translate_api_error(error: genai_errors.APIError) -> LLMError:
    # Only the status is logged: the provider message may echo request content.
    logger.warning("llm_provider_error provider=gemini code=%s status=%s", error.code, error.status)
    if error.code == HTTP_TOO_MANY_REQUESTS:
        return LLMRateLimitError("The language model quota or rate limit is exhausted.")
    if isinstance(error, genai_errors.ServerError):
        return LLMUnavailableError("The language model provider is temporarily unavailable.")
    return LLMError(f"The language model rejected the request (code {error.code}).")


def _to_gemini_tool(tools: Sequence[ToolSpec]) -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.parameters,
            )
            for tool in tools
        ]
    )


def to_gemini_contents(conversation: Sequence[ConversationItem]) -> list[types.Content]:
    """Neutral history -> Gemini ``Content`` list (roles ``user`` / ``model``)."""
    contents: list[types.Content] = []
    for item in conversation:
        if isinstance(item, UserMessage):
            contents.append(types.Content(role="user", parts=[types.Part(text=item.text)]))
        elif isinstance(item, ModelTurn):
            contents.append(_model_content(item))
        elif isinstance(item, ToolResultsMessage):
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=result.call.call_id,
                                name=result.call.name,
                                response=result.content,
                            )
                        )
                        for result in item.results
                    ],
                )
            )
        else:  # pragma: no cover - guarded by the type union
            raise TypeError(f"Unsupported conversation item: {type(item).__name__}")
    return contents


def _model_content(turn: ModelTurn) -> types.Content:
    # Re-use the original content so thought signatures are preserved.
    if isinstance(turn.response.provider_turn, types.Content):
        return turn.response.provider_turn
    parts: list[types.Part] = []
    if turn.response.text:
        parts.append(types.Part(text=turn.response.text))
    parts.extend(
        types.Part(
            function_call=types.FunctionCall(id=call.call_id, name=call.name, args=call.arguments)
        )
        for call in turn.response.tool_calls
    )
    return types.Content(role="model", parts=parts)


def from_gemini_response(response: types.GenerateContentResponse) -> LLMResponse:
    """Gemini response -> neutral ``LLMResponse`` (text, tool calls, usage, finish reason)."""
    candidate = response.candidates[0] if response.candidates else None
    content = candidate.content if candidate is not None else None
    parts = (content.parts or []) if content is not None else []

    texts = [part.text for part in parts if part.text and not part.thought]
    tool_calls = [
        ToolCall(
            name=part.function_call.name or "",
            arguments=dict(part.function_call.args or {}),
            call_id=part.function_call.id,
        )
        for part in parts
        if part.function_call is not None
    ]
    finish_reason = None
    if candidate is not None and candidate.finish_reason is not None:
        finish_reason = getattr(candidate.finish_reason, "value", str(candidate.finish_reason))

    return LLMResponse(
        text="".join(texts) or None,
        tool_calls=tool_calls,
        usage=_usage(response.usage_metadata),
        finish_reason=finish_reason,
        provider_turn=content,
    )


def _usage(metadata: types.GenerateContentResponseUsageMetadata | None) -> TokenUsage:
    if metadata is None:
        return TokenUsage()
    input_tokens = (metadata.prompt_token_count or 0) + (metadata.tool_use_prompt_token_count or 0)
    # Thinking tokens are billed as output, so they count against the output budget.
    output_tokens = (metadata.candidates_token_count or 0) + (metadata.thoughts_token_count or 0)
    total = metadata.total_token_count or (input_tokens + output_tokens)
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total)
