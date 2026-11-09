"""MCP resources – read-only views of budgets and reports (requirement 4.4).

URI parameters are validated by the same Pydantic schemas as tool arguments;
content is the same minimal projection as tool results (JSON, size-limited,
marked as untrusted data).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ResourceError
from pydantic import BaseModel, ValidationError

from shared.ai_tools.gateway import FinanceApiClient, GatewayError
from shared.ai_tools.guardrails import guard_tool_result
from shared.ai_tools.tools import projections
from shared.ai_tools.tools.schemas import (
    FindBudgetByPeriodArgs,
    GetBudgetByCategoriesArgs,
    GetMonthlyReportArgs,
    ToolArguments,
    Year,
)

from app.core.context import McpDependencies

logger = logging.getLogger(__name__)

JSON = "application/json"


class AnnualReportArgs(ToolArguments):
    year: Year


def register_resources(server: MCPServer, deps: McpDependencies) -> None:
    async def read(
        ctx: Context,
        uri: str,
        model: type[BaseModel],
        raw: dict[str, Any],
        load: Callable[[FinanceApiClient, Any], Awaitable[dict[str, Any]]],
    ) -> str:
        try:
            arguments = model.model_validate(raw)
        except ValidationError as error:
            details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors(include_url=False))
            raise ResourceError(f"Invalid resource URI {uri}: {details}") from error
        try:
            async with deps.api_client(ctx) as client:
                content = await load(client, arguments)
        except GatewayError as error:
            raise ResourceError(error.llm_message) from error
        logger.info("mcp_resource uri=%s", uri)
        return json.dumps(guard_tool_result(content, deps.settings.result_max_chars), ensure_ascii=False)

    @server.resource(
        "budget://{year}-{month}/summary",
        name="budget_month_summary",
        title="Budget of a month",
        description="Summary of the user's budget for a month: totals and categories with limits.",
        mime_type=JSON,
    )
    async def budget_month_summary(year: str, month: str, ctx: Context) -> str:
        async def load(client: FinanceApiClient, args: FindBudgetByPeriodArgs) -> dict[str, Any]:
            budgets = await client.find_budgets_by_period(args.period)
            if not budgets:
                return projections.found_budget(budgets, args.period)
            return projections.budget_by_categories(await client.get_budget_summary(budgets[0]["budget_id"]))

        return await read(ctx, f"budget://{year}-{month}/summary", FindBudgetByPeriodArgs, {"year": year, "month": month}, load)

    @server.resource(
        "budget://{budget_id}/categories",
        name="budget_categories",
        title="Budget by categories",
        description="A budget broken down by categories: limit, used, available, limit exceeded.",
        mime_type=JSON,
    )
    async def budget_categories(budget_id: str, ctx: Context) -> str:
        async def load(client: FinanceApiClient, args: GetBudgetByCategoriesArgs) -> dict[str, Any]:
            return projections.budget_by_categories(await client.get_budget_summary(args.budget_id))

        return await read(ctx, f"budget://{budget_id}/categories", GetBudgetByCategoriesArgs, {"budget_id": budget_id}, load)

    @server.resource(
        "report://monthly/{year}/{month}",
        name="monthly_report",
        title="Monthly report",
        description="Monthly report: totals, remaining amount, expenses per category and their shares.",
        mime_type=JSON,
    )
    async def monthly_report(year: str, month: str, ctx: Context) -> str:
        async def load(client: FinanceApiClient, args: GetMonthlyReportArgs) -> dict[str, Any]:
            return projections.monthly_report(await client.get_monthly_report(args.year, args.month))

        return await read(ctx, f"report://monthly/{year}/{month}", GetMonthlyReportArgs, {"year": year, "month": month}, load)

    @server.resource(
        "report://annual/{year}",
        name="annual_report",
        title="Annual report",
        description="Annual report: yearly totals and expenses per month (GET /api/reports/annual/{year}).",
        mime_type=JSON,
    )
    async def annual_report(year: str, ctx: Context) -> str:
        async def load(client: FinanceApiClient, args: AnnualReportArgs) -> dict[str, Any]:
            return projections.annual_report(await client.get_annual_report(args.year))

        return await read(ctx, f"report://annual/{year}", AnnualReportArgs, {"year": year}, load)
