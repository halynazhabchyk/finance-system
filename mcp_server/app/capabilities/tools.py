"""MCP tools – the same five operations as the assistant (requirement 4.3).

Parameters use the shared Pydantic types, so the input schema in MCP Inspector
shows the same constraints. Execution goes through the shared ``ToolExecutor``
(whitelist, validation, API call, projection); results are size-limited and
marked as untrusted data. Failures are returned as ``isError`` tool results.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from shared.ai_tools.guardrails import guard_tool_result
from shared.ai_tools.llm import ToolCall
from shared.ai_tools.tools import TOOL_REGISTRY, ToolExecutor
from shared.ai_tools.tools.schemas import Month, PositiveMoney, SafeDescription, SafeName, Year

from app.core.context import McpDependencies

logger = logging.getLogger(__name__)

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
CREATES_DATA = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False)

BudgetId = Annotated[uuid.UUID, Field(description="budget_id returned by find_budget_by_period.")]
CategoryId = Annotated[uuid.UUID, Field(description="category_id from get_budget_by_categories or create_category.")]


def register_tools(server: MCPServer, deps: McpDependencies) -> None:
    async def run(ctx: Context, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with deps.api_client(ctx) as client:
            execution = await ToolExecutor(client).execute(ToolCall(name=name, arguments=arguments))
        logger.info("mcp_tool tool=%s status=%s duration_ms=%d", name, execution.status, execution.duration_ms)
        if execution.status != "ok":
            raise ToolError(json.dumps(execution.result, ensure_ascii=False))
        return guard_tool_result(execution.result, deps.settings.result_max_chars)

    def describe(name: str) -> str:
        tool = TOOL_REGISTRY[name]
        return f"{tool.description} Endpoint: {tool.endpoint}."

    @server.tool(name="find_budget_by_period", description=describe("find_budget_by_period"), annotations=READ_ONLY)
    async def find_budget_by_period(year: Year, month: Month, ctx: Context) -> dict[str, Any]:
        return await run(ctx, "find_budget_by_period", {"year": year, "month": month})

    @server.tool(name="get_budget_by_categories", description=describe("get_budget_by_categories"), annotations=READ_ONLY)
    async def get_budget_by_categories(budget_id: BudgetId, ctx: Context) -> dict[str, Any]:
        return await run(ctx, "get_budget_by_categories", {"budget_id": str(budget_id)})

    @server.tool(name="create_category", description=describe("create_category"), annotations=CREATES_DATA)
    async def create_category(
        budget_id: BudgetId,
        name: SafeName,
        limit_amount: Annotated[PositiveMoney, Field(description="Monthly limit, > 0, two decimals.")],
        ctx: Context,
    ) -> dict[str, Any]:
        return await run(
            ctx,
            "create_category",
            {"budget_id": str(budget_id), "name": name, "limit_amount": str(limit_amount)},
        )

    @server.tool(name="create_expense", description=describe("create_expense"), annotations=CREATES_DATA)
    async def create_expense(
        budget_id: BudgetId,
        category_id: CategoryId,
        amount: Annotated[PositiveMoney, Field(description="Expense amount, > 0, two decimals.")],
        occurred_at: Annotated[date, Field(description="Date of the expense, YYYY-MM-DD.")],
        ctx: Context,
        description: SafeDescription | None = None,
    ) -> dict[str, Any]:
        return await run(
            ctx,
            "create_expense",
            {
                "budget_id": str(budget_id),
                "category_id": str(category_id),
                "amount": str(amount),
                "occurred_at": occurred_at.isoformat(),
                "description": description,
            },
        )

    @server.tool(name="get_monthly_report", description=describe("get_monthly_report"), annotations=READ_ONLY)
    async def get_monthly_report(year: Year, month: Month, ctx: Context) -> dict[str, Any]:
        return await run(ctx, "get_monthly_report", {"year": year, "month": month})
