"""The five tools: schemas for the model, endpoints, minimal projections (requirements 2.2, 2.3, 2.5)."""

import asyncio
import json

import pytest

from shared.ai_tools.llm import ToolCall
from shared.ai_tools.testing import FakeFinanceApi
from shared.ai_tools.tests.helpers import api_client
from shared.ai_tools.tools import ALLOWED_TOOL_NAMES, ToolExecutor, select_tools

EXPECTED_TOOLS = {
    "find_budget_by_period",
    "get_budget_by_categories",
    "create_category",
    "create_expense",
    "get_monthly_report",
}


def execute(api: FakeFinanceApi, name: str, arguments: dict):
    async def scenario():
        async with api_client(api) as client:
            return await ToolExecutor(client).execute(ToolCall(name=name, arguments=arguments))

    return asyncio.run(scenario())


def test_exactly_five_whitelisted_tools():
    assert ALLOWED_TOOL_NAMES == EXPECTED_TOOLS


def test_tool_specs_have_description_and_simple_schema_without_user_id():
    async def specs():
        async with api_client(FakeFinanceApi()) as client:
            return ToolExecutor(client).tool_specs()

    for spec in asyncio.run(specs()):
        assert spec.description
        assert spec.parameters["type"] == "object"
        assert "user_id" not in spec.parameters["properties"]
        dumped = json.dumps(spec.parameters)
        assert "anyOf" not in dumped and "title" not in dumped  # provider-safe subset


def test_amount_is_number_in_llm_schema():
    (create_expense,) = select_tools(frozenset({"create_expense"}))
    properties = create_expense.spec().parameters["properties"]
    assert properties["amount"]["type"] == "number"
    assert "greater than 0" in properties["amount"]["description"]
    assert properties["occurred_at"]["format"] == "date"
    assert set(create_expense.spec().parameters["required"]) == {"budget_id", "category_id", "amount", "occurred_at"}


def test_select_tools_refuses_names_outside_whitelist():
    with pytest.raises(ValueError):
        select_tools(frozenset({"delete_expense"}))


def test_find_budget_by_period_calls_period_endpoint():
    api = FakeFinanceApi()
    budget_id = api.add_budget("2026-11")

    execution = execute(api, "find_budget_by_period", {"year": 2026, "month": 11})

    assert execution.status == "ok"
    assert api.paths()[-1] == "GET /api/budgets"
    assert api.requests[-1].url.params["period"] == "2026-11"
    assert execution.result == {
        "found": True,
        "budget": {"budget_id": budget_id, "period": "2026-11", "total_amount": "10000.00 UAH"},
    }


def test_find_budget_reports_missing_budget_without_creating_it():
    execution = execute(FakeFinanceApi(), "find_budget_by_period", {"year": 2026, "month": 10})
    assert execution.result["found"] is False
    assert "cannot create" in execution.result["message"]


def test_get_budget_by_categories_returns_minimal_fields():
    api = FakeFinanceApi()
    budget_id = api.add_budget("2026-11")
    api.add_category(budget_id, "Розваги", "2000.00", used="2300.00")

    execution = execute(api, "get_budget_by_categories", {"budget_id": budget_id})

    assert api.paths()[-1] == f"GET /api/budgets/{budget_id}"
    category = execution.result["categories"][0]
    assert category["name"] == "Розваги"
    assert category["available_amount"] == "-300.00 UAH"
    assert category["limit_exceeded"] is True
    serialized = json.dumps(execution.result)
    for hidden in ("user_id", "instance_id", "created_at", "expenses", "service"):
        assert hidden not in serialized


def test_create_category_posts_to_budget():
    api = FakeFinanceApi()
    budget_id = api.add_budget("2026-11")

    execution = execute(api, "create_category", {"budget_id": budget_id, "name": "Продукти", "limit_amount": 3000})

    assert api.paths()[-1] == f"POST /api/budgets/{budget_id}/categories"
    assert json.loads(api.requests[-1].content) == {"name": "Продукти", "limit_amount": "3000"}
    assert execution.result["status"] == "created"
    assert execution.result["limit_amount"] == "3000.00 UAH"


def test_create_expense_returns_expense_id_saga_status_and_pending_note():
    api = FakeFinanceApi()
    budget_id = api.add_budget("2026-11")
    category_id = api.add_category(budget_id, "Продукти", "3000.00")

    execution = execute(
        api,
        "create_expense",
        {"budget_id": budget_id, "category_id": category_id, "amount": 250, "occurred_at": "2026-11-08", "description": "Сільпо"},
    )

    assert api.paths()[-1] == f"POST /api/budgets/{budget_id}/expenses"
    assert execution.result["expense_id"]
    assert execution.result["saga_status"] == "PENDING"
    assert "SAGA" in execution.result["note"]
    assert execution.result["amount"] == "250.00 UAH"


def test_get_monthly_report_returns_category_shares():
    api = FakeFinanceApi()
    api.add_report(2026, 11, [("Продукти", "3000.00", "1250.00", "62.50"), ("Розваги", "2000.00", "750.00", "37.50")])

    execution = execute(api, "get_monthly_report", {"year": 2026, "month": 11})

    assert api.paths()[-1] == "GET /api/reports/monthly/2026/11"
    assert execution.result["total_expenses"] == "2000.00 UAH"
    assert execution.result["categories"][0] == {
        "name": "Продукти",
        "limit_amount": "3000.00 UAH",
        "total_expenses": "1250.00 UAH",
        "share_of_expenses_percent": "62.50",
    }


def test_api_error_is_returned_to_model_as_tool_result():
    execution = execute(FakeFinanceApi(), "get_monthly_report", {"year": 2026, "month": 1})
    assert execution.status == "error"
    assert "Monthly report is not available yet" in execution.result["message"]
