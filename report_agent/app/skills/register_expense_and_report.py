"""Skill ``register_expense_and_report`` – A2A integration with budget-agent (requirement 5.5).

1. resolve the Agent Card of budget-agent (through the gateway);
2. create an A2A task ``register_expense`` with the same user JWT;
3. follow the task states (SUBMITTED -> WORKING -> COMPLETED / FAILED);
4. after COMPLETED (SAGA completed, expense CONFIRMED) read the updated monthly report;
   after FAILED report the reason (SAGA cancelled: DLQ or TIMEOUT).

RabbitMQ is not involved here: the SAGA itself still runs on domain events
between Budget Service and Report Service.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from shared.ai_tools.a2a.client import RemoteAgentClient, RemoteAgentError
from shared.ai_tools.a2a.server import SkillContext, SkillFailed
from shared.ai_tools.tools import projections
from shared.ai_tools.tools.schemas import CreateExpenseArgs

from app.services.explainer import Explainer

logger = logging.getLogger(__name__)

REMOTE_SKILL = "register_expense"

RemoteAgentFactory = Callable[[str], RemoteAgentClient]


class RegisterExpenseAndReportSkill:
    def __init__(self, *, remote_factory: RemoteAgentFactory, explainer: Explainer) -> None:
        self._remote_factory = remote_factory
        self._explainer = explainer

    async def __call__(self, ctx: SkillContext) -> None:
        # Guardrail: validate before delegating, so an invalid request never reaches another agent.
        args = CreateExpenseArgs.model_validate(ctx.request.arguments)

        async def relay(state: str, text: str) -> None:
            if state not in {"COMPLETED", "FAILED", "REJECTED"}:
                await ctx.working(f"budget-agent task: {state}. {text}".strip())

        try:
            async with self._remote_factory(ctx.access_token) as remote:
                card = await remote.discover(REMOTE_SKILL)
                await ctx.working(f"Agent Card of '{card.name}' {card.version} resolved; creating task '{REMOTE_SKILL}'.")
                result = await remote.run_skill(REMOTE_SKILL, args.model_dump(mode="json"), on_state=relay)
        except RemoteAgentError as error:
            raise SkillFailed(str(error)) from error

        logger.info(
            "a2a_delegation_finished agent=report-agent task_id=%s remote_task_id=%s remote_states=%s",
            ctx.task_id,
            result.task_id,
            "->".join(result.states),
        )
        if not result.succeeded:
            failure = result.artifacts.get("failure", {})
            raise SkillFailed(
                f"budget-agent task {result.task_id} ended {result.state}: {result.message}",
                {"remote_task_id": result.task_id, "remote_states": result.states, **failure},
            )

        expense = result.artifacts.get("expense", {})
        report = projections.monthly_report(
            await ctx.api.get_monthly_report(args.occurred_at.year, args.occurred_at.month)
        )
        data = {"remote_task_id": result.task_id, "remote_states": result.states, "expense": expense, "monthly_report": report}
        await ctx.artifact("expense_and_report", data)
        explanation = await self._explainer.explain(
            ctx.api,
            "An expense was just confirmed by the SAGA. Tell the user it is registered and summarise the updated report.",
            data,
            request_id=ctx.task_id[:12],
        )
        await ctx.complete(
            explanation
            or f"Expense {expense.get('expense_id')} is CONFIRMED. Report {report['period']}: expenses "
            f"{report['total_expenses']}, remaining {report['remaining']}."
        )
