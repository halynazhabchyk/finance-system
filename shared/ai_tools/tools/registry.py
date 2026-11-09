"""The whitelist: exactly five tools (requirement 2.2). No update/delete tools exist."""

from __future__ import annotations

from typing import Any

from shared.ai_tools.gateway.client import FinanceApiClient
from shared.ai_tools.tools import projections
from shared.ai_tools.tools.definitions import ToolDefinition
from shared.ai_tools.tools.schemas import (
    CreateCategoryArgs,
    CreateExpenseArgs,
    FindBudgetByPeriodArgs,
    GetBudgetByCategoriesArgs,
    GetMonthlyReportArgs,
)


async def _find_budget_by_period(client: FinanceApiClient, args: FindBudgetByPeriodArgs) -> dict[str, Any]:
    budgets = await client.find_budgets_by_period(args.period)
    return projections.found_budget(budgets, args.period)


async def _get_budget_by_categories(client: FinanceApiClient, args: GetBudgetByCategoriesArgs) -> dict[str, Any]:
    return projections.budget_by_categories(await client.get_budget_summary(args.budget_id))


async def _create_category(client: FinanceApiClient, args: CreateCategoryArgs) -> dict[str, Any]:
    payload = {"name": args.name, "limit_amount": str(args.limit_amount)}
    return projections.created_category(await client.create_category(args.budget_id, payload))


async def _create_expense(client: FinanceApiClient, args: CreateExpenseArgs) -> dict[str, Any]:
    payload = {
        "category_id": str(args.category_id),
        "amount": str(args.amount),
        "occurred_at": args.occurred_at.isoformat(),
        "description": args.description,
    }
    return projections.created_expense(await client.create_expense(args.budget_id, payload))


async def _get_monthly_report(client: FinanceApiClient, args: GetMonthlyReportArgs) -> dict[str, Any]:
    return projections.monthly_report(await client.get_monthly_report(args.year, args.month))


FIND_BUDGET_BY_PERIOD = ToolDefinition(
    name="find_budget_by_period",
    description=(
        "Find the user's budget for a calendar month and get its budget_id. Call this first "
        "whenever you need a budget_id and the user names a month (e.g. 'листопад 2026')."
    ),
    args_model=FindBudgetByPeriodArgs,
    endpoint="GET /api/budgets?period=YYYY-MM",
    handler=_find_budget_by_period,
)

GET_BUDGET_BY_CATEGORIES = ToolDefinition(
    name="get_budget_by_categories",
    description=(
        "Get a budget broken down by categories: total amount, used and available amount of the "
        "budget, and for each category its category_id, name, limit, used, available amount and "
        "whether the limit is exceeded. Use it to answer 'how much can I still spend', to find a "
        "category_id by name, or to check that a category exists before creating it."
    ),
    args_model=GetBudgetByCategoriesArgs,
    endpoint="GET /api/budgets/{budget_id}",
    handler=_get_budget_by_categories,
)

CREATE_CATEGORY = ToolDefinition(
    name="create_category",
    description=(
        "Create a category with a monthly limit in a budget. Call it only if "
        "get_budget_by_categories shows that a category with this name does not exist yet "
        "and the user asked for it or agreed to it."
    ),
    args_model=CreateCategoryArgs,
    endpoint="POST /api/budgets/{budget_id}/categories",
    handler=_create_category,
)

CREATE_EXPENSE = ToolDefinition(
    name="create_expense",
    description=(
        "Register an expense in a category of a budget. Returns expense_id and saga_status. "
        "The status is PENDING at first: the expense appears in reports only after the SAGA "
        "confirms it. Requires budget_id and category_id obtained from other tools."
    ),
    args_model=CreateExpenseArgs,
    endpoint="POST /api/budgets/{budget_id}/expenses",
    handler=_create_expense,
)

GET_MONTHLY_REPORT = ToolDefinition(
    name="get_monthly_report",
    description=(
        "Get the monthly report: total budget, total expenses, remaining amount and expenses per "
        "category with their share of all expenses. Use it for analysis and for comparing months "
        "(call it once per month)."
    ),
    args_model=GetMonthlyReportArgs,
    endpoint="GET /api/reports/monthly/{year}/{month}",
    handler=_get_monthly_report,
)

ALL_TOOLS: tuple[ToolDefinition, ...] = (
    FIND_BUDGET_BY_PERIOD,
    GET_BUDGET_BY_CATEGORIES,
    CREATE_CATEGORY,
    CREATE_EXPENSE,
    GET_MONTHLY_REPORT,
)
TOOL_REGISTRY: dict[str, ToolDefinition] = {tool.name: tool for tool in ALL_TOOLS}
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(TOOL_REGISTRY)


def select_tools(names: frozenset[str] | None = None) -> tuple[ToolDefinition, ...]:
    """A subset of the whitelist (e.g. read-only tools for report-agent)."""
    if names is None:
        return ALL_TOOLS
    unknown = names - ALLOWED_TOOL_NAMES
    if unknown:
        raise ValueError(f"Tools outside the whitelist: {sorted(unknown)}")
    return tuple(tool for tool in ALL_TOOLS if tool.name in names)
