"""Function-calling loop with a scripted LLM (requirement 2.4, limits of 3.1)."""

import asyncio

from shared.ai_tools.agent import FunctionCallingLoop
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.testing import (
    FakeFinanceApi,
    ScriptedLLMClient,
    final_answer,
    latest_tool_result as _last_result,
    tool_call_response,
)
from shared.ai_tools.tests.helpers import api_client
from shared.ai_tools.tools import ToolExecutor


def run_loop(api, llm, limits=AgentLimits(), message="Привіт"):
    async def scenario():
        async with api_client(api) as client:
            loop = FunctionCallingLoop(llm=llm, executor=ToolExecutor(client), system_prompt="SYSTEM", limits=limits)
            return await loop.run(message)

    return asyncio.run(scenario())


def test_model_receives_tools_and_tool_results_until_final_answer():
    api = FakeFinanceApi()
    api.add_budget("2026-11")
    llm = ScriptedLLMClient(
        [
            tool_call_response(("find_budget_by_period", {"year": 2026, "month": 11})),
            final_answer("Бюджет на листопад знайдено."),
        ]
    )

    result = run_loop(api, llm)

    assert result.stopped_reason == "completed"
    assert result.answer == "Бюджет на листопад знайдено."
    assert [call.name for call in result.tool_calls] == ["find_budget_by_period"]
    assert {tool.name for tool in llm.requests[0].tools} == {
        "find_budget_by_period", "get_budget_by_categories", "create_category", "create_expense", "get_monthly_report",
    }
    assert llm.last_tool_results()[0]["found"] is True
    assert result.usage.total_tokens == 200
    assert result.iterations == 2


def test_chain_add_expense_with_missing_category():
    """«Додай витрату 250 грн на продукти в бюджет за листопад 2026. Якщо категорії немає – створи її»."""
    api = FakeFinanceApi()
    api.add_budget("2026-11")

    def get_categories(conversation):
        budget_id = _last_result(conversation)["budget"]["budget_id"]
        return tool_call_response(("get_budget_by_categories", {"budget_id": budget_id}))

    def create_category(conversation):
        summary = _last_result(conversation)
        assert summary["categories"] == []  # the model sees there is no "Продукти"
        return tool_call_response(
            ("create_category", {"budget_id": summary["budget_id"], "name": "Продукти", "limit_amount": 3000})
        )

    def create_expense(conversation):
        category = _last_result(conversation)
        return tool_call_response(
            (
                "create_expense",
                {"budget_id": category["budget_id"], "category_id": category["category_id"], "amount": 250, "occurred_at": "2026-11-08"},
            )
        )

    llm = ScriptedLLMClient(
        [
            tool_call_response(("find_budget_by_period", {"year": 2026, "month": 11})),
            get_categories,
            create_category,
            create_expense,
            final_answer("Витрату 250.00 UAH прийнято (PENDING), вона з'явиться у звіті після підтвердження SAGA."),
        ]
    )

    result = run_loop(api, llm)

    assert [call.name for call in result.tool_calls] == [
        "find_budget_by_period",
        "get_budget_by_categories",
        "create_category",
        "create_expense",
    ]
    assert all(call.status == "ok" for call in result.tool_calls)
    assert llm.last_tool_results()[0]["saga_status"] == "PENDING"
    assert len(api.expenses) == 1


def test_loop_stops_after_max_iterations():
    api = FakeFinanceApi()
    llm = ScriptedLLMClient([tool_call_response(("find_budget_by_period", {"year": 2026, "month": 11}))] * 2)

    result = run_loop(api, llm, AgentLimits(max_tool_iterations=2))

    assert result.stopped_reason == "max_iterations"
    assert "ліміту кроків (2)" in result.answer
    assert len(llm.requests) == 2


def test_loop_stops_when_token_budget_is_exhausted_without_another_model_call():
    api = FakeFinanceApi()
    llm = ScriptedLLMClient(
        [
            tool_call_response(("find_budget_by_period", {"year": 2026, "month": 11}), tokens=600),
            final_answer("не має бути викликано"),
        ]
    )

    result = run_loop(api, llm, AgentLimits(max_tokens_per_request=500))

    assert result.stopped_reason == "token_budget_exceeded"
    assert "600 із 500" in result.answer
    assert len(llm.requests) == 1
    assert result.tool_calls == []  # the requested tool was not executed either


def test_empty_answer_cut_by_max_output_tokens_is_reported():
    llm = ScriptedLLMClient([final_answer("", finish_reason="MAX_TOKENS")])

    result = run_loop(FakeFinanceApi(), llm)

    assert result.stopped_reason == "output_truncated"
    assert "ліміт вихідних токенів" in result.answer
