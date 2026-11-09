"""Runs tool calls requested by a model: whitelist -> validation -> API -> projection."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from shared.ai_tools.gateway.client import FinanceApiClient
from shared.ai_tools.gateway.errors import GatewayError
from shared.ai_tools.llm.client import ToolCall, ToolSpec
from shared.ai_tools.tools.definitions import ToolDefinition
from shared.ai_tools.tools.registry import ALL_TOOLS

logger = logging.getLogger(__name__)

ToolStatus = Literal["ok", "rejected", "invalid_arguments", "error"]


@dataclass(frozen=True)
class ToolExecution:
    """Outcome of one tool call; ``result`` is what the model receives."""

    name: str
    arguments: dict[str, Any]
    status: ToolStatus
    result: dict[str, Any]
    duration_ms: int


class ToolExecutor:
    """Executes calls of the whitelisted tools on behalf of one user (one API client)."""

    def __init__(
        self,
        client: FinanceApiClient,
        *,
        tools: tuple[ToolDefinition, ...] = ALL_TOOLS,
    ) -> None:
        self._client = client
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools)

    def tool_specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    async def execute(self, call: ToolCall) -> ToolExecution:
        started = time.perf_counter()
        tool = self._tools.get(call.name)
        if tool is None:
            logger.warning("tool_rejected reason=not_whitelisted tool=%r", call.name[:80])
            return self._finish(
                call,
                "rejected",
                {
                    "error": "tool_not_allowed",
                    "message": f"Tool '{call.name}' is not available. Only these tools exist: "
                    f"{', '.join(self._tools)}. Deleting or changing data is not possible.",
                },
                started,
            )

        try:
            arguments = tool.args_model.model_validate(call.arguments)
        except ValidationError as error:
            logger.info("tool_invalid_arguments tool=%s errors=%d", call.name, error.error_count())
            return self._finish(
                call,
                "invalid_arguments",
                {
                    "error": "invalid_arguments",
                    "message": "The arguments were rejected before calling the API. Fix them or ask the user.",
                    "details": _validation_details(error),
                },
                started,
            )

        try:
            result = await tool.handler(self._client, arguments)
        except GatewayError as error:
            logger.info("tool_api_error tool=%s status=%s", call.name, error.status_code)
            return self._finish(call, "error", {"error": "api_error", "message": error.llm_message}, started)

        return self._finish(call, "ok", result, started)

    @staticmethod
    def _finish(call: ToolCall, status: ToolStatus, result: dict[str, Any], started: float) -> ToolExecution:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info("tool_call tool=%s status=%s duration_ms=%d", call.name[:80], status, duration_ms)
        return ToolExecution(
            name=call.name,
            arguments=dict(call.arguments),
            status=status,
            result=result,
            duration_ms=duration_ms,
        )


def _validation_details(error: ValidationError) -> list[str]:
    details = []
    for item in error.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in item["loc"]) or "arguments"
        details.append(f"{location}: {item['msg']}")
    return details
