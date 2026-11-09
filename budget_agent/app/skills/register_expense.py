"""Skill ``register_expense``: create an expense and follow its SAGA to the end.

Structured requests go straight to the API (validated by the shared schema).
Free-text requests are handled by the function-calling loop with four of the
whitelisted tools; the agent then follows the SAGA of the created expense.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from shared.ai_tools.a2a.server import SkillContext, SkillFailed
from shared.ai_tools.agent import FunctionCallingLoop
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.llm import LLMClient, ToolCall
from shared.ai_tools.tools import ToolExecutor, select_tools
from shared.ai_tools.tools.schemas import CreateExpenseArgs

from app.core.prompts import REGISTER_EXPENSE_PROMPT
from app.services.saga_tracker import wait_for_saga

logger = logging.getLogger(__name__)

TEXT_TOOLS = frozenset({"find_budget_by_period", "get_budget_by_categories", "create_category", "create_expense"})
CREATE_EXPENSE_TOOL = select_tools(frozenset({"create_expense"}))


class RegisterExpenseSkill:
    def __init__(
        self,
        *,
        llm_factory: Callable[[], LLMClient | None],
        limits: AgentLimits,
        saga_wait_seconds: float,
        saga_poll_interval_seconds: float,
        sleep=None,
    ) -> None:
        self._llm_factory = llm_factory
        self._limits = limits
        self._saga_wait = saga_wait_seconds
        self._saga_interval = saga_poll_interval_seconds
        self._sleep = sleep

    async def __call__(self, ctx: SkillContext) -> None:
        expense = await (self._from_data(ctx) if ctx.request.is_structured else self._from_text(ctx))
        if expense is None:
            return
        await self._follow_saga(ctx, expense)

    async def _from_data(self, ctx: SkillContext) -> dict[str, Any]:
        args = CreateExpenseArgs.model_validate(ctx.request.arguments)
        execution = await ToolExecutor(ctx.api, tools=CREATE_EXPENSE_TOOL).execute(
            ToolCall(name="create_expense", arguments=args.model_dump(mode="json"))
        )
        if execution.status != "ok":
            raise SkillFailed(execution.result.get("message", "The expense was not created."), execution.result)
        return execution.result

    async def _from_text(self, ctx: SkillContext) -> dict[str, Any] | None:
        llm = self._llm_factory()
        if llm is None:
            await ctx.reject("Free-text requests need the language model (LLM_API_KEY); send structured data instead.")
            return None
        loop = FunctionCallingLoop(
            llm=llm,
            executor=ToolExecutor(ctx.api, tools=select_tools(TEXT_TOOLS)),
            system_prompt=REGISTER_EXPENSE_PROMPT,
            limits=self._limits,
        )
        result = await loop.run(ctx.request.text, request_id=ctx.task_id[:12])
        created = [call for call in result.tool_calls if call.name == "create_expense" and call.status == "ok"]
        if result.stopped_reason != "completed":
            raise SkillFailed(result.answer)
        if not created:
            # The model needs more information (month, category, amount ...).
            await ctx.require_input(result.answer)
            return None
        await ctx.working(result.answer)
        return created[-1].result

    async def _follow_saga(self, ctx: SkillContext, expense: dict[str, Any]) -> None:
        expense_id, budget_id = uuid.UUID(expense["expense_id"]), uuid.UUID(expense["budget_id"])
        await ctx.working(
            f"Expense {expense_id} accepted with saga_status PENDING. Budget Service published ExpenseCreated "
            "through the Outbox; waiting for the SAGA."
        )

        async def progress(status: str) -> None:
            await ctx.working(f"SAGA of expense {expense_id}: {status}.")

        kwargs = {"sleep": self._sleep} if self._sleep else {}
        outcome = await wait_for_saga(
            ctx.api,
            budget_id,
            expense_id,
            timeout_seconds=self._saga_wait,
            poll_interval_seconds=self._saga_interval,
            on_progress=progress,
            **kwargs,
        )
        data = {**expense, "saga_id": outcome.saga_id, "saga_status": outcome.expense_status}
        data.pop("note", None)
        if outcome.status == "COMPLETED":
            await ctx.artifact("expense", data)
            await ctx.complete(f"Expense {expense_id} is CONFIRMED: the SAGA completed and the report includes it.")
            return
        if outcome.status == "CANCELLED":
            data.update(failure_reason=outcome.failure_reason, failure_details=outcome.failure_details)
            raise SkillFailed(
                f"SAGA cancelled the expense {expense_id} (reason: {outcome.failure_reason}). "
                "It is not counted in limits and reports.",
                data,
            )
        raise SkillFailed(
            f"The SAGA of expense {expense_id} is still {outcome.status} after {self._saga_wait:.0f} s; "
            "check its state later with GET /api/budgets/{budget_id}/expenses/{expense_id}/saga.",
            data,
        )
