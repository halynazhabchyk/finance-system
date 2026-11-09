"""Analytical skills of report-agent: monthly analysis, limit exceedances, comparison of months."""

from __future__ import annotations

from collections.abc import Callable

from shared.ai_tools.a2a.server import SkillContext, SkillFailed
from shared.ai_tools.agent import FunctionCallingLoop
from shared.ai_tools.config import AgentLimits
from shared.ai_tools.llm import LLMClient
from shared.ai_tools.tools import ToolExecutor, projections, select_tools

from app.core.prompts import ANALYSIS_PROMPT
from app.services import analytics
from app.services.explainer import Explainer
from app.skills.schemas import ComparePeriodsArgs, MonthArgs

READ_ONLY_TOOLS = frozenset({"find_budget_by_period", "get_budget_by_categories", "get_monthly_report"})


class AnalysisSkills:
    def __init__(self, *, explainer: Explainer, llm_factory: Callable[[], LLMClient | None], limits: AgentLimits) -> None:
        self._explainer = explainer
        self._llm_factory = llm_factory
        self._limits = limits

    async def analyze_monthly_spending(self, ctx: SkillContext) -> None:
        if not ctx.request.is_structured:
            await self._answer_free_text(ctx)
            return
        args = MonthArgs.model_validate(ctx.request.arguments)
        report = projections.monthly_report(await ctx.api.get_monthly_report(args.year, args.month))
        await ctx.artifact("monthly_report", report)
        await self._finish(ctx, args.explain, f"Analyse spending of {args.period} by categories.", report,
                           f"Monthly report for {args.period}: expenses {report['total_expenses']}, remaining {report['remaining']}.")

    async def detect_limit_exceedances(self, ctx: SkillContext) -> None:
        args = MonthArgs.model_validate(ctx.request.arguments)
        budgets = await ctx.api.find_budgets_by_period(args.period)
        if not budgets:
            raise SkillFailed(f"There is no budget for {args.period}.")
        result = analytics.limit_exceedances(await ctx.api.get_budget_summary(budgets[0]["budget_id"]))
        await ctx.artifact("limit_exceedances", result)
        summary = (
            f"{result['exceeded_count']} of {result['checked_categories']} categories exceed their limit in {args.period}: "
            + (", ".join(f"{item['name']} (+{item['overrun']})" for item in result["exceeded"]) or "none")
            + "."
        )
        await self._finish(ctx, args.explain, f"Explain limit exceedances in {args.period} and possible reasons.", result, summary)

    async def compare_periods(self, ctx: SkillContext) -> None:
        args = ComparePeriodsArgs.model_validate(ctx.request.arguments)
        first = await ctx.api.get_monthly_report(args.first.year, args.first.month)
        second = await ctx.api.get_monthly_report(args.second.year, args.second.month)
        result = analytics.compare_reports(first, second)
        await ctx.artifact("comparison", result)
        summary = (
            f"Total expenses {result['first_period']} -> {result['second_period']}: change {result['total_expenses']['change']}. "
            f"Increased in: {', '.join(result['increased']) or 'no category'}."
        )
        await self._finish(ctx, args.explain, "Compare expenses of the two months by category.", result, summary)

    async def _answer_free_text(self, ctx: SkillContext) -> None:
        llm = self._llm_factory()
        if llm is None:
            await ctx.reject("Free-text questions need the language model (LLM_API_KEY); send structured data instead.")
            return
        loop = FunctionCallingLoop(
            llm=llm,
            executor=ToolExecutor(ctx.api, tools=select_tools(READ_ONLY_TOOLS)),
            system_prompt=ANALYSIS_PROMPT,
            limits=self._limits,
        )
        result = await loop.run(ctx.request.text, request_id=ctx.task_id[:12])
        await ctx.artifact(
            "analysis",
            {
                "tool_calls": [{"name": call.name, "status": call.status} for call in result.tool_calls],
                "total_tokens": result.usage.total_tokens,
                "stopped_reason": result.stopped_reason,
            },
        )
        if result.stopped_reason != "completed":
            raise SkillFailed(result.answer)
        await ctx.complete(result.answer)

    async def _finish(self, ctx: SkillContext, explain: bool, task: str, data: dict, fallback: str) -> None:
        explanation = await self._explainer.explain(ctx.api, task, data, request_id=ctx.task_id[:12]) if explain else None
        await ctx.complete(explanation or fallback)
