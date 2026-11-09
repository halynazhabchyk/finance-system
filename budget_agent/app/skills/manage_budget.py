"""Skill ``manage_budget``: create a budget or a category (deterministic, no LLM – decision Р1)."""

from __future__ import annotations

from pydantic import TypeAdapter

from shared.ai_tools.a2a.server import SkillContext, SkillFailed
from shared.ai_tools.llm import ToolCall
from shared.ai_tools.tools import ToolExecutor, select_tools
from shared.ai_tools.tools import projections

from app.skills.schemas import CreateBudgetArgs, ManageBudgetArgs

_ARGS = TypeAdapter(ManageBudgetArgs)
CREATE_CATEGORY_TOOL = select_tools(frozenset({"create_category"}))


async def manage_budget(ctx: SkillContext) -> None:
    if not ctx.request.is_structured:
        await ctx.reject("manage_budget accepts structured data only (no language model is used).")
        return
    args = _ARGS.validate_python(ctx.request.arguments)

    if isinstance(args, CreateBudgetArgs):
        budget = await ctx.api.create_budget(args.to_payload())
        await ctx.artifact("budget", projections.budget_reference(budget))
        await ctx.complete(f"Budget {budget['budget_id']} for {args.year:04d}-{args.month:02d} created (event BudgetCreated).")
        return

    execution = await ToolExecutor(ctx.api, tools=CREATE_CATEGORY_TOOL).execute(
        ToolCall(name="create_category", arguments=args.model_dump(mode="json", exclude={"action"}))
    )
    if execution.status != "ok":
        raise SkillFailed(execution.result.get("message", "The category was not created."), execution.result)
    await ctx.artifact("category", execution.result)
    await ctx.complete(f"Category '{execution.result['name']}' created (event BudgetUpdated).")
